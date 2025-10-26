# musictheorybench/validation/l1_rules.py
"""
包含所有L1层级（结构框架）的验证规则。
包括：节奏、调性、声部进行。
"""
from typing import List, Dict, Tuple, Optional, Set
from models import Note, Pitch


class L1RulesMixin:

    # ========== L1.3: Rhythmic Structure ==========
    def check_L1_rhythmic_structure_complete(self) -> List[Dict]:
        errors = []
        measures = self._group_notes_by_measure()
        for measure_num, measure_voices in measures.items():
            for voice_num, notes in measure_voices.items():
                errors.extend(self._check_measure_duration_accuracy(measure_num, voice_num, notes))
                errors.extend(self._check_metric_accent_placement(measure_num, voice_num, notes))
                errors.extend(self._check_rhythm_pattern_coherence(measure_num, voice_num, notes))
        return errors

    def _check_measure_duration_accuracy(self, measure_num: int, voice_num: int, notes: List[Note]) -> List[Dict]:
        errors = []
        total_duration = sum(note.duration for note in notes if not note.is_chord_tone or note == notes[0])
        expected_duration = self.time_signature[0] * self.parser.divisions
        tolerance = self.parser.divisions * 0.1
        if abs(total_duration - expected_duration) > tolerance:
            errors.append({
                'type': 'measure_duration_mismatch', 'level': 'L1',
                'location': {'measure': measure_num, 'voice': voice_num},
                'message': f'小节{measure_num}声部{voice_num}时值不匹配: 实际{total_duration}d, 期望{expected_duration}d',
                'severity': min(5, int(abs(total_duration - expected_duration) / self.parser.divisions))
            })
        return errors

    def _check_metric_accent_placement(self, measure_num: int, voice_num: int, notes: List[Note]) -> List[Dict]:
        errors = []
        if self.time_signature == (4, 4):
            beat_strengths = {0.0: 1.0, 1.0: 0.3, 2.0: 0.7, 3.0: 0.3}
            for note in notes:
                if note.is_rest or note.is_chord_tone: continue
                beat_pos = note.beat_position
                rounded_beat = round(beat_pos)
                if rounded_beat in beat_strengths:
                    expected_strength = beat_strengths[rounded_beat]
                    actual_strength = self._calculate_note_metric_weight(note)
                    if expected_strength > 0.8 and actual_strength < 0.2:
                        errors.append({
                            'type': 'weak_note_on_strong_beat', 'level': 'L1',
                            'location': {'measure': measure_num, 'voice': voice_num, 'beat': beat_pos},
                            'message': f'强拍位置({rounded_beat + 1})使用了明显偏弱的音符', 'severity': 2
                        })
                    elif expected_strength < 0.2 and actual_strength > 0.9:
                        errors.append({
                            'type': 'strong_accent_on_weak_beat', 'level': 'L1',
                            'location': {'measure': measure_num, 'voice': voice_num, 'beat': beat_pos},
                            'message': f'弱拍位置({rounded_beat + 1})使用了过分强调的重音', 'severity': 2
                        })
        return errors

    def _calculate_note_metric_weight(self, note: Note) -> float:
        weight = 0.5
        duration_weights = {'whole': 1.0, 'half': 0.8, 'quarter': 0.5, 'eighth': 0.3, 'sixteenth': 0.2,
                            'thirty-second': 0.1}
        weight *= duration_weights.get(note.note_type, 0.5)
        if note.pitch:
            semitone_height = note.pitch.to_semitones()
            if semitone_height < 36 or semitone_height > 84:
                weight *= 1.3
            elif 48 <= semitone_height <= 72:
                weight *= 0.9
        if note.is_tied: weight *= 0.7
        return min(weight, 1.0)

    def _check_rhythm_pattern_coherence(self, measure_num: int, voice_num: int, notes: List[Note]) -> List[Dict]:
        errors = []
        rhythm_pattern = [
            {'duration': n.duration, 'type': n.note_type, 'beat_pos': n.beat_position, 'is_rest': n.is_rest} for n in
            notes if not n.is_chord_tone]
        if len(rhythm_pattern) > 12 and self._calculate_rhythm_complexity(rhythm_pattern) > 0.9:
            errors.append({
                'type': 'overly_complex_rhythm', 'level': 'L1',
                'location': {'measure': measure_num, 'voice': voice_num},
                'message': f'小节{measure_num}节奏极其复杂', 'severity': 2
            })
        for i in range(len(rhythm_pattern) - 1):
            current, next_note = rhythm_pattern[i], rhythm_pattern[i + 1]
            if current['duration'] <= self.parser.divisions // 8 and next_note['duration'] >= self.parser.divisions * 3:
                errors.append({
                    'type': 'jarring_rhythm_transition', 'level': 'L1',
                    'location': {'measure': measure_num, 'voice': voice_num},
                    'message': f'小节{measure_num}节奏转换极其突兀: {current["type"]} → {next_note["type"]}',
                    'severity': 1
                })
        return errors

    def _calculate_rhythm_complexity(self, pattern: List[Dict]) -> float:
        if not pattern: return 0.0
        complexity = len(set(p['duration'] for p in pattern)) / 6.0
        changes = sum(1 for i in range(len(pattern) - 1) if pattern[i]['duration'] != pattern[i + 1]['duration'])
        complexity += changes / len(pattern)
        syncopation_count = sum(1 for p in pattern if p['beat_pos'] % 1.0 != 0.0 and not p['is_rest'])
        complexity += syncopation_count / len(pattern)
        return min(complexity, 1.0)

    # ========== L1.1: Tonal Consistency ==========
    def check_L1_tonal_consistency_complete(self) -> List[Dict]:
        errors = []
        expected_accidentals = self._get_key_signature_accidentals()
        for voice_num, notes in self.voices.items():
            for note in notes:
                if note.is_rest or note.pitch is None: continue
                errors.extend(self._check_basic_key_compliance(note, expected_accidentals, voice_num))
                errors.extend(self._check_tonal_context(note, voice_num))
        errors.extend(self._check_tonal_stability())
        return errors

    def _check_basic_key_compliance(self, note: Note, expected_accidentals: Dict[str, int], voice_num: int) -> List[
        Dict]:
        errors = []
        step, actual_alter = note.pitch.step, note.pitch.alter
        if step in expected_accidentals:
            expected_alter = expected_accidentals[step]
            if actual_alter != expected_alter:
                errors.append({
                    'type': 'key_signature_violation', 'level': 'L1',
                    'location': {'voice': voice_num, 'measure': note.measure},
                    'message': f'{step}{actual_alter}违反调号要求(应为{step}{expected_alter})',
                    'severity': 4
                })
        elif actual_alter != 0 and not self._is_reasonable_chromatic_alteration(note):
            errors.append({
                'type': 'unjustified_accidental', 'level': 'L1',
                'location': {'voice': voice_num, 'measure': note.measure},
                'message': f'{step}{actual_alter}的变音记号缺乏理论依据', 'severity': 2
            })
        return errors

    def _is_reasonable_chromatic_alteration(self, note: Note) -> bool:
        if note.pitch.alter == 1 and (note.pitch.to_semitones() + 1) % 12 == self._get_key_tonic_semitone() % 12:
            return True
        if note.pitch.alter == -1: return True
        return note.pitch.alter in [-1, 1]

    def _check_tonal_context(self, note: Note, voice_num: int) -> List[Dict]:
        errors = []
        if not self._is_in_scale(note.pitch):
            severity = self._calculate_scale_deviation_severity(note.pitch)
            if severity > 0.5:
                errors.append({
                    'type': 'scale_deviation', 'level': 'L1',
                    'location': {'voice': voice_num, 'measure': note.measure},
                    'message': f'音符{note.pitch}偏离当前调性', 'severity': min(5, int(severity * 5))
                })
        return errors

    def _is_in_scale(self, pitch: Pitch) -> bool:
        return pitch.to_semitones() % 12 in self._get_scale_pitch_classes()

    def _calculate_scale_deviation_severity(self, pitch: Pitch) -> float:
        pitch_class = pitch.to_semitones() % 12
        scale_pitches = self._get_scale_pitch_classes()
        min_distance = min(abs(pitch_class - sp) for sp in scale_pitches)
        min_distance = min(min_distance, 12 - min_distance)
        return min_distance / 6.0

    def _check_tonal_stability(self) -> List[Dict]:
        errors = []
        pitch_class_count = defaultdict(int)
        total_notes = 0
        for voice_notes in self.voices.values():
            for note in voice_notes:
                if not note.is_rest and note.pitch:
                    pitch_class_count[note.pitch.to_semitones() % 12] += 1
                    total_notes += 1
        if total_notes == 0: return errors

        key_tonic = self._get_key_tonic_semitone()
        if (pitch_class_count[key_tonic] / total_notes) < 0.05:
            errors.append({'type': 'weak_tonal_center', 'level': 'L1', 'location': {'global': True},
                           'message': '调性中心极其不稳定', 'severity': 3})

        scale_pitches = self._get_scale_pitch_classes()
        out_of_scale_count = sum(count for pc, count in pitch_class_count.items() if pc not in scale_pitches)
        if (out_of_scale_count / total_notes) > 0.4:
            errors.append({'type': 'excessive_chromatic_content', 'level': 'L1', 'location': {'global': True},
                           'message': '调外音过多', 'severity': 3})
        return errors

    # ========== L1.2: Voice Leading ==========
    def check_L1_voice_leading_complete(self) -> List[Dict]:
        if len(self.voices) < 2: return []
        errors = []
        time_aligned_voices = self._create_precise_time_alignment()
        voice_pairs = self._get_voice_pairs()
        for v1, v2 in voice_pairs:
            errors.extend(self._analyze_voice_pair_comprehensive(v1, v2, time_aligned_voices))
        return errors

    def _create_precise_time_alignment(self) -> Dict[float, Dict[int, Optional[Note]]]:
        all_time_points = set()
        for notes in self.voices.values():
            for note in notes:
                all_time_points.add((note.measure - 1) * self.time_signature[0] + note.beat_position)

        aligned_voices = {}
        for time_point in sorted(all_time_points):
            aligned_voices[time_point] = {}
            for voice_num in self.voices.keys():
                best_note = None
                min_distance = float('inf')
                for note in self.voices[voice_num]:
                    note_time = (note.measure - 1) * self.time_signature[0] + note.beat_position
                    distance = abs(note_time - time_point)
                    if distance < min_distance and distance < 0.1:
                        min_distance, best_note = distance, note
                aligned_voices[time_point][voice_num] = best_note
        return aligned_voices

    def _get_voice_pairs(self) -> List[Tuple[int, int]]:
        voice_numbers = list(self.voices.keys())
        return [(voice_numbers[i], voice_numbers[j]) for i in range(len(voice_numbers)) for j in
                range(i + 1, len(voice_numbers))]

    def _analyze_voice_pair_comprehensive(self, v1: int, v2: int,
                                          aligned_voices: Dict[float, Dict[int, Optional[Note]]]) -> List[Dict]:
        errors = []
        time_points = sorted(aligned_voices.keys())
        for i in range(len(time_points) - 1):
            current_time, next_time = time_points[i], time_points[i + 1]
            current_pair = (aligned_voices[current_time].get(v1), aligned_voices[current_time].get(v2))
            next_pair = (aligned_voices[next_time].get(v1), aligned_voices[next_time].get(v2))
            if self._is_valid_voice_pair(current_pair, next_pair):
                errors.extend(self._check_parallel_motion_comprehensive(current_pair, next_pair, v1, v2, current_time))
                errors.extend(self._check_hidden_parallels(current_pair, next_pair, v1, v2, current_time))
                errors.extend(self._check_voice_crossing_comprehensive(current_pair, next_pair, v1, v2, current_time))
                errors.extend(self._check_voice_spacing(current_pair, next_pair, v1, v2, current_time))
        return errors

    def _is_valid_voice_pair(self, current_pair: Tuple[Optional[Note], Optional[Note]],
                             next_pair: Tuple[Optional[Note], Optional[Note]]) -> bool:
        notes = current_pair + next_pair
        return all(n is not None and not n.is_rest and n.pitch is not None for n in notes)

    def _check_parallel_motion_comprehensive(self, c_pair: Tuple[Note, Note], n_pair: Tuple[Note, Note], v1: int,
                                             v2: int, time: float) -> List[Dict]:
        errors = []
        n1a, n2a = c_pair
        n1b, n2b = n_pair
        int1, int2 = n1a.pitch.interval_to(n2a.pitch), n1b.pitch.interval_to(n2b.pitch)
        perfect_intervals = {1, 4, 5, 8}
        if (
                int1.generic_interval in perfect_intervals and int1.generic_interval == int2.generic_interval and int1.quality == 'perfect' and int2.quality == 'perfect'):
            if n1a.pitch.to_semitones() != n1b.pitch.to_semitones() or n2a.pitch.to_semitones() != n2b.pitch.to_semitones():
                errors.append({
                    'type': 'parallel_perfect_intervals', 'level': 'L1',
                    'location': {'voices': [v1, v2], 'measure': n1a.measure, 'time_point': time},
                    'message': f'平行{int1.generic_interval}度: 声部{v1}({n1a.pitch}→{n1b.pitch}) 声部{v2}({n2a.pitch}→{n2b.pitch})',
                    'severity': self._calculate_parallel_motion_severity(int1.generic_interval)
                })
        return errors

    def _calculate_parallel_motion_severity(self, interval: int) -> int:
        return {1: 5, 8: 5, 5: 4, 4: 2}.get(interval, 3)

    def _check_hidden_parallels(self, c_pair: Tuple[Note, Note], n_pair: Tuple[Note, Note], v1: int, v2: int,
                                time: float) -> List[Dict]:
        errors = []
        n1a, n2a = c_pair
        n1b, n2b = n_pair
        dir1 = self._get_melodic_direction(n1a.pitch, n1b.pitch)
        dir2 = self._get_melodic_direction(n2a.pitch, n2b.pitch)
        if dir1 == dir2 and dir1 != 'static':
            final_interval = n1b.pitch.interval_to(n2b.pitch)
            if final_interval.generic_interval in {1, 4, 5, 8} and final_interval.quality == 'perfect':
                leap1 = abs(n1b.pitch.to_semitones() - n1a.pitch.to_semitones()) > 2
                leap2 = abs(n2b.pitch.to_semitones() - n2a.pitch.to_semitones()) > 2
                if leap1 or leap2:
                    errors.append({
                        'type': 'hidden_parallel_intervals', 'level': 'L1',
                        'location': {'voices': [v1, v2], 'measure': n1a.measure, 'time_point': time},
                        'message': f'隐藏平行{final_interval.generic_interval}度', 'severity': 2
                    })
        return errors

    def _get_melodic_direction(self, pitch1: Pitch, pitch2: Pitch) -> str:
        s1, s2 = pitch1.to_semitones(), pitch2.to_semitones()
        if s2 > s1:
            return 'ascending'
        elif s2 < s1:
            return 'descending'
        else:
            return 'static'

    def _check_voice_crossing_comprehensive(self, c_pair: Tuple[Note, Note], n_pair: Tuple[Note, Note], v1: int,
                                            v2: int, time: float) -> List[Dict]:
        errors = []
        if v1 < v2:
            upper_voice, lower_voice = (c_pair[0], n_pair[0]), (c_pair[1], n_pair[1])
            upper_num, lower_num = v1, v2
        else:
            upper_voice, lower_voice = (c_pair[1], n_pair[1]), (c_pair[0], n_pair[0])
            upper_num, lower_num = v2, v1

        upper_current, upper_next = upper_voice
        lower_current, lower_next = lower_voice

        if upper_current.pitch.to_semitones() < lower_current.pitch.to_semitones():
            errors.append({'type': 'voice_crossing_static', 'level': 'L1',
                           'location': {'voices': [upper_num, lower_num], 'measure': upper_current.measure,
                                        'time_point': time},
                           'message': f'声部交叉: 上声部{upper_num}({upper_current.pitch}) < 下声部{lower_num}({lower_current.pitch})',
                           'severity': 3})

        if upper_current.pitch.to_semitones() >= lower_current.pitch.to_semitones() and upper_next.pitch.to_semitones() < lower_next.pitch.to_semitones():
            errors.append({'type': 'voice_crossing_motion', 'level': 'L1',
                           'location': {'voices': [upper_num, lower_num], 'measure': upper_current.measure,
                                        'time_point': time},
                           'message': f'声部进行中发生交叉: 上声部{upper_num} 与 下声部{lower_num}', 'severity': 3})
        return errors

    def _check_voice_spacing(self, c_pair: Tuple[Note, Note], n_pair: Tuple[Note, Note], v1: int, v2: int,
                             time: float) -> List[Dict]:
        errors = []
        n1a, n2a = c_pair
        current_distance = abs(n1a.pitch.to_semitones() - n2a.pitch.to_semitones())
        if current_distance > 24:
            errors.append({'type': 'excessive_voice_spacing', 'level': 'L1',
                           'location': {'voices': [v1, v2], 'measure': n1a.measure, 'time_point': time},
                           'message': f'声部间距过大: {current_distance}半音', 'severity': 2})
        if 0 < current_distance < 1:
            errors.append({'type': 'insufficient_voice_spacing', 'level': 'L1',
                           'location': {'voices': [v1, v2], 'measure': n1a.measure, 'time_point': time},
                           'message': '声部间距过小: 微分音程', 'severity': 4})
        return errors
