# musictheorybench/validation/l0_rules.py
"""
包含所有L0层级（基础音乐元素）的验证规则。
"""
from typing import List, Dict, Set, Tuple
from models import Pitch, Note


class L0RulesMixin:

    def check_L0_complete(self) -> List[Dict]:
        """完整的L0层检测，包括所有注入错误类型"""
        errors = []
        errors.extend(self.check_L0_pitch_spelling())
        errors.extend(self.check_L0_intervals())
        errors.extend(self.check_L0_chord_construction())
        errors.extend(self.check_L0_octave_displacement())
        errors.extend(self.check_L0_pitch_substitution())
        return errors

    def check_L0_pitch_spelling(self) -> List[Dict]:
        """增强的L0.1: 检测音高拼写问题，包括等音错误"""
        errors = []
        for voice_num, notes in self.voices.items():
            for i, note in enumerate(notes):
                if note.is_rest or note.pitch is None:
                    continue
                already = False
                if self._is_poor_enharmonic_spelling(note.pitch):
                    errors.append({
                        'type': 'poor_enharmonic_spelling', 'level': 'L0',
                        'location': {'voice': voice_num, 'measure': note.measure},
                        'message': f'Poor enharmonic spelling: {note.pitch}',
                        'pitch': note.pitch, 'severity': 1
                    })
                    already = True
                if (not already) and self._is_injected_enharmonic_error(note.pitch):
                    errors.append({
                        'type': 'enharmonic_error', 'level': 'L0',
                        'location': {'voice': voice_num, 'measure': note.measure},
                        'message': f'Injected enharmonic error: {note.pitch}',
                        'pitch': note.pitch, 'severity': 2
                    })
        return errors

    def _is_poor_enharmonic_spelling(self, pitch: Pitch) -> bool:
        """判断是否为不良的等音拼写"""
        return (pitch.step == 'E' and pitch.alter == 1) or \
            (pitch.step == 'B' and pitch.alter == 1) or \
            (pitch.step == 'F' and pitch.alter == -1) or \
            (pitch.step == 'C' and pitch.alter == -1)

    def _is_injected_enharmonic_error(self, pitch: Pitch) -> bool:
        key_fifths = self.key_signature['fifths']
        expected = self._get_key_signature_accidentals()
        if pitch.step in expected and expected[pitch.step] == pitch.alter:
            return False
        if key_fifths > 0 and pitch.alter < 0:
            return True
        if key_fifths < 0 and pitch.alter > 0:
            return True
        return f"{pitch.step}{pitch.alter}" in {'E1', 'B1', 'F-1', 'C-1'}

    def check_L0_intervals(self) -> List[Dict]:
        """L0.2: 检测音程的基础问题"""
        errors = []
        for voice_num, notes in self.voices.items():
            melodic_notes = [n for n in notes if not n.is_rest and n.pitch is not None]
            for i in range(len(melodic_notes) - 1):
                note1, note2 = melodic_notes[i], melodic_notes[i + 1]
                if getattr(note1, "_octave_flagged", False) or getattr(note2, "_octave_flagged", False):
                    continue
                interval = note1.pitch.interval_to(note2.pitch)
                semitone_distance = abs(note2.pitch.to_semitones() - note1.pitch.to_semitones())
                if semitone_distance > 24:
                    errors.append({
                        'type': 'excessive_leap', 'level': 'L0',
                        'location': {'voice': voice_num, 'measure': note1.measure},
                        'message': f'过大跳跃({semitone_distance}半音): {note1.pitch}→{note2.pitch}',
                        'interval': interval, 'semitone_distance': semitone_distance, 'severity': 3
                    })
                if interval.quality == 'augmented' and interval.generic_interval in [4, 5]:
                    if not self._is_tritone_contextually_justified(note1, note2):
                        errors.append({
                            'type': 'unjustified_tritone', 'level': 'L0',
                            'location': {'voice': voice_num, 'measure': note1.measure},
                            'message': f'缺乏依据的{interval.quality}{interval.generic_interval}度: {note1.pitch}→{note2.pitch}',
                            'interval': interval, 'severity': 2
                        })
        return errors

    def _is_tritone_contextually_justified(self, note1: Note, note2: Note) -> bool:
        return True

    def check_L0_chord_construction(self) -> List[Dict]:
        """L0.3: 检测和弦构成的基础问题"""
        errors = []
        chords = self._extract_simultaneous_notes()
        for chord_data in chords:
            if len(chord_data['notes']) < 3: continue
            pitches = [note.pitch for note in chord_data['notes'] if note.pitch is not None]
            chord_quality = self._analyze_chord_quality_simple(pitches)
            if chord_quality['type'] == 'unrecognized':
                errors.append({
                    'type': 'unrecognized_chord_structure', 'level': 'L0',
                    'location': {'measure': chord_data['measure'], 'beat': chord_data['beat_position']},
                    'message': f'无法识别的和弦结构: {[str(p) for p in pitches]}',
                    'chord_pitches': pitches, 'severity': 3
                })
            if self._has_basic_voice_crossing(chord_data['notes']):
                errors.append({
                    'type': 'voice_crossing_in_chord', 'level': 'L0',
                    'location': {'measure': chord_data['measure'], 'beat': chord_data['beat_position']},
                    'message': '和弦内声部交叉', 'chord_pitches': pitches, 'severity': 2
                })
            if self._has_cluster_intervals(pitches):
                errors.append({
                    'type': 'cluster_intervals', 'level': 'L0',
                    'location': {'measure': chord_data['measure'], 'beat': chord_data['beat_position']},
                    'message': '和弦音程排列过于密集', 'chord_pitches': pitches, 'severity': 2
                })
        return errors

    def _analyze_chord_quality_simple(self, pitches: List[Pitch]) -> Dict[str, any]:
        if len(pitches) < 3:
            return {'type': 'incomplete', 'quality': None}
        pitch_classes = sorted(set(p.to_semitones() % 12 for p in pitches))
        if len(pitch_classes) >= 3:
            intervals = sorted([(pc - pitch_classes[0]) % 12 for pc in pitch_classes])
            chord_patterns = {
                (0, 3, 7): {'type': 'minor_triad', 'quality': 'minor'},
                (0, 4, 7): {'type': 'major_triad', 'quality': 'major'},
                (0, 3, 6): {'type': 'diminished_triad', 'quality': 'diminished'},
                (0, 4, 8): {'type': 'augmented_triad', 'quality': 'augmented'}
            }
            return chord_patterns.get(tuple(intervals[:3]), {'type': 'unrecognized', 'quality': 'unknown'})
        return {'type': 'unrecognized', 'quality': 'unknown'}

    def _has_basic_voice_crossing(self, notes: List[Note]) -> bool:
        if any(n.voice is None for n in notes) or len(notes) < 2: return False
        sorted_by_voice = sorted(notes, key=lambda n: n.voice)
        for i in range(len(sorted_by_voice) - 1):
            if sorted_by_voice[i].pitch.to_semitones() > sorted_by_voice[i + 1].pitch.to_semitones():
                return True
        return False

    def _has_cluster_intervals(self, pitches: List[Pitch]) -> bool:
        if len(pitches) < 3: return False
        semitones = sorted([p.to_semitones() for p in pitches])
        cluster_count = sum(1 for i in range(len(semitones) - 1) if semitones[i + 1] - semitones[i] <= 2)
        return cluster_count > len(semitones) // 2

    def check_L0_octave_displacement(self) -> List[Dict]:
        """检测八度错位问题"""
        errors = []
        flagged_pitch_ids: Set[Tuple[int, int, int]] = set()
        for voice_num, notes in self.voices.items():
            for i, note in enumerate(notes):
                if note.is_rest or note.pitch is None: continue
                pitch_id = (voice_num, note.measure, note.pitch.to_semitones())
                if pitch_id in flagged_pitch_ids: continue
                if self._is_octave_displacement(note.pitch, voice_num):
                    errors.append({
                        'type': 'octave_displacement', 'level': 'L0',
                        'location': {'voice': voice_num, 'measure': note.measure, 'note_index': i},
                        'message': f'八度错位: {note.pitch} 在声部{voice_num}中音域不合理',
                        'pitch': note.pitch, 'severity': 2
                    })
                    flagged_pitch_ids.add(pitch_id)
                if i > 0:
                    prev_note = notes[i - 1]
                    if prev_note.pitch and not prev_note.is_rest:
                        leap = abs(note.pitch.to_semitones() - prev_note.pitch.to_semitones())
                        if leap > 19:
                            errors.append({
                                'type': 'extreme_melodic_leap', 'level': 'L0',
                                'location': {'voice': voice_num, 'measure': note.measure},
                                'message': f'极端旋律跳跃: {prev_note.pitch}→{note.pitch} ({leap}半音)',
                                'severity': 3
                            })
        return errors

    def _is_octave_displacement(self, pitch: Pitch, voice_num: int) -> bool:
        semitone_height = pitch.to_semitones()
        voice_ranges = {1: (48, 84), 2: (36, 72), 3: (24, 60), 4: (12, 48)}
        expected_range = voice_ranges.get(voice_num, (24, 84))
        if voice_num >= 5: expected_range = (24, 72)
        return semitone_height < expected_range[0] or semitone_height > expected_range[1]

    def check_L0_pitch_substitution(self) -> List[Dict]:
        """检测音高替换错误"""
        errors = []
        for voice_num, notes in self.voices.items():
            for i, note in enumerate(notes):
                if note.is_rest or note.pitch is None: continue
                if self._is_pitch_substitution_error(note):
                    errors.append({
                        'type': 'pitch_substitution', 'level': 'L0',
                        'location': {'voice': voice_num, 'measure': note.measure, 'note_index': i},
                        'message': f'音高替换错误: {note.pitch} 在当前和声语境中不合理',
                        'pitch': note.pitch, 'severity': 3
                    })
        return errors

    def _is_pitch_substitution_error(self, note: Note) -> bool:
        prev_note = self._get_prev_melodic_note(note)
        if prev_note:
            semitone_diff = abs(note.pitch.to_semitones() - prev_note.pitch.to_semitones())
            if note.pitch.step == prev_note.pitch.step and semitone_diff in (1, 2):
                if not self._is_injected_enharmonic_error(note.pitch):
                    return True
        if not self._is_in_scale(note.pitch):
            return self._calculate_scale_deviation_severity(note.pitch) > 0.15
        if prev_note:
            leap = abs(note.pitch.to_semitones() - prev_note.pitch.to_semitones())
            if 12 < leap < 15:
                return True
        return False
