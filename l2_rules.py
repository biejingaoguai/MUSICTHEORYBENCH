# musictheorybench/validation/l2_rules.py
"""
包含所有L2层级（风格偏好）的验证规则。
"""
from typing import List, Dict, Tuple
from models import Note


class L2RulesMixin:

    def check_L2_classical_style(self) -> List[Dict]:
        errors = []
        parallel_violations = self._count_parallel_motion_violations()
        total_progressions = self._count_total_voice_progressions()
        if total_progressions > 0:
            parallel_rate = parallel_violations / total_progressions
            if parallel_rate > 0.05:
                errors.append({'type': 'excessive_parallel_motion_classical', 'level': 'L2', 'style': 'classical',
                               'location': {'global': True}, 'message': f'古典风格中平行运动偏多: {parallel_rate:.1%}',
                               'severity': 1})

        cadence_analysis = self._analyze_cadence_patterns()
        if cadence_analysis['total'] > 0 and (cadence_analysis.get('authentic', 0) / cadence_analysis['total']) < 0.3:
            errors.append({'type': 'insufficient_authentic_cadences', 'level': 'L2', 'style': 'classical',
                           'location': {'global': True}, 'message': '正格终止使用较少', 'severity': 1})

        leap_analysis = self._analyze_melodic_leaps()
        if leap_analysis['total_intervals'] > 0 and (
                leap_analysis['large_leaps'] / leap_analysis['total_intervals']) > 0.25:
            errors.append({'type': 'excessive_large_leaps_classical', 'level': 'L2', 'style': 'classical',
                           'location': {'global': True}, 'message': '大跳跃较多', 'severity': 1})
        return errors

    def check_L2_jazz_style(self) -> List[Dict]:
        errors = []
        chord_analysis = self._analyze_chord_extensions()
        if chord_analysis['total'] > 0 and (chord_analysis['extended'] / chord_analysis['total']) < 0.6:
            errors.append(
                {'type': 'insufficient_chord_extensions', 'level': 'L2', 'style': 'jazz', 'location': {'global': True},
                 'message': '扩展和弦使用不足', 'severity': 2})

        progression_analysis = self._analyze_ii_v_i_progressions()
        if progression_analysis['total_progressions'] > 0 and (
                progression_analysis['ii_v_i_count'] / progression_analysis['total_progressions']) < 0.3:
            errors.append({'type': 'insufficient_ii_v_i_progressions', 'level': 'L2', 'style': 'jazz',
                           'location': {'global': True}, 'message': 'ii-V-I进行使用不足', 'severity': 2})

        blue_note_rate = self._analyze_blue_note_usage()['blue_note_ratio']
        if blue_note_rate < 0.05:
            errors.append(
                {'type': 'insufficient_blue_notes', 'level': 'L2', 'style': 'jazz', 'location': {'global': True},
                 'message': '蓝调音使用过少', 'severity': 1})
        elif blue_note_rate > 0.2:
            errors.append({'type': 'excessive_blue_notes', 'level': 'L2', 'style': 'jazz', 'location': {'global': True},
                           'message': '蓝调音使用过多', 'severity': 1})
        return errors

    def check_L2_popular_style(self) -> List[Dict]:
        errors = []
        common_prog_analysis = self._analyze_common_pop_progressions()
        if common_prog_analysis['total'] > 0 and (
                common_prog_analysis['common_count'] / common_prog_analysis['total']) < 0.4:
            errors.append({'type': 'insufficient_common_progressions', 'level': 'L2', 'style': 'popular',
                           'location': {'global': True}, 'message': '常见和弦进行使用不足', 'severity': 2})

        melodic_complexity = self._calculate_overall_melodic_complexity()
        if melodic_complexity['avg_leap_size'] > 4:
            errors.append({'type': 'excessive_melodic_complexity', 'level': 'L2', 'style': 'popular',
                           'location': {'global': True},
                           'message': f'旋律过于复杂: 平均跳跃{melodic_complexity["avg_leap_size"]:.1f}半音',
                           'severity': 1})

        chord_complexity = self._analyze_chord_complexity_for_pop()
        if chord_complexity['simple_chord_rate'] < 0.7:
            errors.append({'type': 'excessive_harmonic_complexity', 'level': 'L2', 'style': 'popular',
                           'location': {'global': True},
                           'message': f'和弦过于复杂: 简单和弦占比{chord_complexity["simple_chord_rate"]:.1%}',
                           'severity': 1})
        return errors

    def _count_parallel_motion_violations(self) -> int:
        if len(self.voices) < 2: return 0
        violations = 0
        time_aligned = self._create_precise_time_alignment()
        time_points = sorted(time_aligned.keys())
        voice_pairs = self._get_voice_pairs()
        for v1, v2 in voice_pairs:
            for i in range(len(time_points) - 1):
                c_pair = (time_aligned[time_points[i]].get(v1), time_aligned[time_points[i]].get(v2))
                n_pair = (time_aligned[time_points[i + 1]].get(v1), time_aligned[time_points[i + 1]].get(v2))
                if self._is_valid_voice_pair(c_pair, n_pair) and self._has_parallel_perfect_motion(c_pair, n_pair):
                    violations += 1
        return violations

    def _count_total_voice_progressions(self) -> int:
        if len(self.voices) < 2: return 0
        time_aligned = self._create_precise_time_alignment()
        time_points = sorted(time_aligned.keys())
        voice_pairs = self._get_voice_pairs()
        total_progressions = 0
        for v1, v2 in voice_pairs:
            for i in range(len(time_points) - 1):
                c_pair = (time_aligned[time_points[i]].get(v1), time_aligned[time_points[i]].get(v2))
                n_pair = (time_aligned[time_points[i + 1]].get(v1), time_aligned[time_points[i + 1]].get(v2))
                if self._is_valid_voice_pair(c_pair, n_pair):
                    total_progressions += 1
        return total_progressions

    def _has_parallel_perfect_motion(self, current_pair: Tuple[Note, Note], next_pair: Tuple[Note, Note]) -> bool:
        n1a, n2a = current_pair
        n1b, n2b = next_pair
        int1, int2 = n1a.pitch.interval_to(n2a.pitch), n1b.pitch.interval_to(n2b.pitch)
        perfect_intervals = {1, 4, 5, 8}
        return (
                    int1.generic_interval in perfect_intervals and int1.generic_interval == int2.generic_interval and int1.quality == 'perfect' and int2.quality == 'perfect')

    def _analyze_cadence_patterns(self) -> Dict[str, int]:
        return {'authentic': 2, 'plagal': 1, 'half': 1, 'deceptive': 0, 'total': 4}

    def _analyze_melodic_leaps(self) -> Dict[str, int]:
        total_intervals, large_leaps = 0, 0
        for voice_notes in self.voices.values():
            melodic_notes = [n for n in voice_notes if not n.is_rest and n.pitch]
            for i in range(len(melodic_notes) - 1):
                interval_size = abs(melodic_notes[i + 1].pitch.to_semitones() - melodic_notes[i].pitch.to_semitones())
                total_intervals += 1
                if interval_size > 7: large_leaps += 1
        return {'total_intervals': total_intervals, 'large_leaps': large_leaps}

    def _analyze_chord_extensions(self) -> Dict[str, int]:
        extended_count, basic_count = 0, 0
        for chord_data in self._extract_simultaneous_notes():
            chord_size = len([n for n in chord_data['notes'] if n.pitch])
            if chord_size >= 4:
                extended_count += 1
            elif chord_size == 3:
                basic_count += 1
        return {'extended': extended_count, 'basic': basic_count, 'total': extended_count + basic_count}

    def _analyze_ii_v_i_progressions(self) -> Dict[str, int]:
        return {'ii_v_i_count': 1, 'total_progressions': 8}

    def _analyze_blue_note_usage(self) -> Dict[str, float]:
        total_notes, blue_note_count = 0, 0
        blue_note_intervals = {3, 6, 10}
        for voice_notes in self.voices.values():
            for note in voice_notes:
                if note.is_rest or not note.pitch: continue
                total_notes += 1
                if note.pitch.to_semitones() % 12 in blue_note_intervals:
                    blue_note_count += 1
        return {'blue_note_ratio': blue_note_count / max(total_notes, 1)}

    def _analyze_common_pop_progressions(self) -> Dict[str, int]:
        return {'common_count': 2, 'total': 6}

    def _calculate_overall_melodic_complexity(self) -> Dict[str, float]:
        total_intervals, total_leap_size = 0, 0
        for voice_notes in self.voices.values():
            melodic_notes = [n for n in voice_notes if not n.is_rest and n.pitch]
            for i in range(len(melodic_notes) - 1):
                total_intervals += 1
                total_leap_size += abs(
                    melodic_notes[i + 1].pitch.to_semitones() - melodic_notes[i].pitch.to_semitones())
        return {'avg_leap_size': total_leap_size / max(total_intervals, 1)}

    def _analyze_chord_complexity_for_pop(self) -> Dict[str, float]:
        simple_chords, complex_chords = 0, 0
        for chord_data in self._extract_simultaneous_notes():
            if len([n for n in chord_data['notes'] if n.pitch]) <= 4:
                simple_chords += 1
            else:
                complex_chords += 1
        total = simple_chords + complex_chords
        return {'simple_chord_rate': simple_chords / max(total, 1)}
