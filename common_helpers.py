# musictheorybench/validation/common_helpers.py
"""
包含被多个验证层级共用的辅助函数。
"""
from typing import Dict, Set, List, Optional
from collections import defaultdict
from fractions import Fraction
from models import Note, Pitch


class CommonHelpersMixin:

    def _get_key_signature_accidentals(self) -> Dict[str, int]:
        """根据调号获取预期的变音记号"""
        fifths = self.key_signature['fifths']
        if fifths == 0:
            return {}
        elif fifths > 0:
            sharp_order = ['F', 'C', 'G', 'D', 'A', 'E', 'B']
            return {sharp_order[i]: 1 for i in range(min(fifths, 7))}
        else:
            flat_order = ['B', 'E', 'A', 'D', 'G', 'C', 'F']
            return {flat_order[i]: -1 for i in range(min(abs(fifths), 7))}

    def _get_key_tonic_semitone(self) -> int:
        """获取调性主音的半音数"""
        fifths = self.key_signature['fifths']
        tonic_map = {
            -7: 11, -6: 6, -5: 1, -4: 8, -3: 3, -2: 10, -1: 5,
            0: 0,
            1: 7, 2: 2, 3: 9, 4: 4, 5: 11, 6: 6, 7: 1
        }
        return tonic_map.get(fifths, 0)

    def _get_scale_pitch_classes(self) -> Set[int]:
        """获取当前调性的音阶音高类集合"""
        key_root = self._get_key_tonic_semitone()
        if self.key_signature['mode'] == 'major':
            scale_intervals = [0, 2, 4, 5, 7, 9, 11]
        else:
            scale_intervals = [0, 2, 3, 5, 7, 8, 10]
        return {(key_root + interval) % 12 for interval in scale_intervals}

    def _group_notes_by_measure(self) -> Dict[int, Dict[int, List[Note]]]:
        """按小节和声部组织音符"""
        measures = defaultdict(lambda: defaultdict(list))
        for voice_num, notes in self.voices.items():
            for note in notes:
                measures[note.measure][voice_num].append(note)
        for measure_num in measures:
            for voice_num in measures[measure_num]:
                measures[measure_num][voice_num].sort(key=lambda n: n.beat_position)
        return measures

    def _get_prev_melodic_note(self, note: Note) -> Optional[Note]:
        notes = self.voices[note.voice]
        try:
            idx = notes.index(note)
            for j in range(idx - 1, -1, -1):
                if not notes[j].is_rest and notes[j].pitch:
                    return notes[j]
        except ValueError:
            pass  # note not in list
        return None

    def _extract_simultaneous_notes(self) -> List[Dict]:
        """提取同时发声的音符组合成和弦"""
        chords = []
        time_points = defaultdict(list)

        for voice_num, notes in self.voices.items():
            for note in notes:
                if not note.is_rest and note.pitch is not None:
                    time_key = (note.measure, Fraction(note.beat_position).limit_denominator(32))
                    time_points[time_key].append(note)

        for (measure, beat_pos), notes in time_points.items():
            if len({n.pitch.to_semitones() for n in notes}) < 3:
                continue
            if any(n.duration < self.parser.divisions * 2 for n in notes):
                continue
            if len({n.voice for n in notes}) < 2:
                continue

            chords.append({
                'notes': notes,
                'measure': measure,
                'beat_position': beat_pos
            })

        return chords

