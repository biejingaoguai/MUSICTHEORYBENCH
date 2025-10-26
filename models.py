# musictheorybench/models.py
"""
包含项目核心数据模型: Pitch, Interval, Note.
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class Pitch:
    """MusicXML pitch的直接表示"""
    step: str  # C, D, E, F, G, A, B
    alter: int = 0  # -2到+2，表示降降、降、自然、升、升升
    octave: int = 4

    def __post_init__(self):
        if self.step not in ['C', 'D', 'E', 'F', 'G', 'A', 'B']:
            raise ValueError(f"Invalid step: {self.step}")

    def to_semitones(self) -> int:
        """转换为相对于C0的半音数，仅用于音程计算"""
        steps = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
        return steps[self.step] + self.alter + (self.octave + 1) * 12

    def interval_to(self, other: 'Pitch') -> 'Interval':
        """计算到另一个音高的音程"""
        return Interval.from_pitches(self, other)

    def __str__(self):
        alter_str = '♯' * self.alter if self.alter > 0 else '♭' * abs(self.alter) if self.alter < 0 else ''
        return f"{self.step}{alter_str}{self.octave}"

@dataclass
class Interval:
    """音程的理论表示"""
    generic_interval: int  # 1-8 (一度到八度)
    quality: str  # 'perfect', 'major', 'minor', 'augmented', 'diminished'
    direction: str = 'ascending'  # 'ascending' or 'descending'

    @classmethod
    def from_pitches(cls, pitch1: Pitch, pitch2: Pitch) -> 'Interval':
        """从两个音高计算音程"""
        step_order = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
        step1_idx = step_order.index(pitch1.step)
        step2_idx = step_order.index(pitch2.step)

        octave_diff = pitch2.octave - pitch1.octave
        generic = (step2_idx - step1_idx + octave_diff * 7) + 1

        semitones = pitch2.to_semitones() - pitch1.to_semitones()

        quality = cls._determine_quality(abs(generic), abs(semitones))
        direction = 'ascending' if semitones >= 0 else 'descending'

        return cls(abs(generic), quality, direction)

    @staticmethod
    def _determine_quality(generic: int, semitones: int) -> str:
        """根据度数和半音数确定音程性质"""
        interval_map = {
            1: {0: 'perfect', 1: 'augmented'},
            2: {1: 'minor', 2: 'major', 3: 'augmented'},
            3: {3: 'minor', 4: 'major', 5: 'augmented'},
            4: {5: 'perfect', 6: 'augmented', 4: 'diminished'},
            5: {7: 'perfect', 8: 'augmented', 6: 'diminished'},
            6: {8: 'minor', 9: 'major', 10: 'augmented'},
            7: {10: 'minor', 11: 'major', 12: 'augmented'},
            8: {12: 'perfect', 13: 'augmented'}
        }

        reduced_generic = ((generic - 1) % 7) + 1
        octaves = (generic - 1) // 7
        reduced_semitones = semitones - octaves * 12

        return interval_map.get(reduced_generic, {}).get(reduced_semitones, 'unknown')

    def is_consonant(self) -> bool:
        """判断是否为协和音程"""
        consonant_intervals = {
            (1, 'perfect'), (4, 'perfect'), (5, 'perfect'), (8, 'perfect'),
            (3, 'major'), (3, 'minor'), (6, 'major'), (6, 'minor')
        }
        return (self.generic_interval, self.quality) in consonant_intervals

@dataclass
class Note:
    """MusicXML note的完整表示"""
    pitch: Optional[Pitch] = None
    duration: int = 4
    note_type: str = 'quarter'
    is_rest: bool = False
    is_chord_tone: bool = False
    measure: int = 1
    staff: int = 1
    voice: int = 1
    beat_position: float = 0.0
    is_tied: bool = False

    def __str__(self):
        if self.is_rest:
            return f"Rest({self.note_type})"
        return f"Note({self.pitch}, {self.note_type})"
