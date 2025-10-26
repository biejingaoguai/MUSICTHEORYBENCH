# musictheorybench/parser.py
"""
包含 StandardMusicXMLParser 类，负责解析 .xml 和 .mxl 文件。
"""
import os
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from models import Pitch, Note, Interval


class StandardMusicXMLParser:
    """标准MusicXML解析器，完整处理MusicXML结构"""

    def __init__(self, xml_input):
        self.root = None
        self.tree = None

        if isinstance(xml_input, ET.Element):
            self.root = xml_input
        elif isinstance(xml_input, str):
            if os.path.isfile(xml_input):
                try:
                    print(f"正在解析文件: {xml_input}")
                    if xml_input.lower().endswith('.mxl'):
                        print("检测到MXL压缩文件，正在解压...")
                        with zipfile.ZipFile(xml_input, 'r') as zip_file:
                            xml_files = [f for f in zip_file.namelist() if
                                         f.endswith('.xml') and not f.lower().startswith('meta-inf/')]
                            if not xml_files:
                                raise ValueError("MXL文件中未找到XML内容")

                            main_xml = xml_files[0]
                            if len(xml_files) > 1:
                                for f in xml_files:
                                    if 'score' in f.lower() or 'music' in f.lower():
                                        main_xml = f
                                        break

                            print(f"正在解析MXL内的文件: {main_xml}")
                            with zip_file.open(main_xml) as xml_content:
                                self.root = ET.parse(xml_content).getroot()
                    else:
                        self.tree = ET.parse(xml_input)
                        self.root = self.tree.getroot()
                    print(f"文件解析成功!")
                except ET.ParseError as e:
                    print(f"文件XML解析错误: {e}")
                    raise
                except Exception as e:
                    print(f"文件读取错误: {e}")
                    raise
            else:
                try:
                    print("正在解析XML字符串...")
                    self.root = ET.fromstring(xml_input)
                    print("XML字符串解析成功!")
                except ET.ParseError as e:
                    print(f"XML字符串解析错误: {e}")
                    raise
        else:
            raise TypeError(f"不支持的输入类型: {type(xml_input)}")

        self.divisions = 4

    def extract_key_signature(self) -> Dict[str, any]:
        key_elem = self.root.find('.//key')
        if key_elem is None:
            return {'fifths': 0, 'mode': 'major'}
        fifths_elem = key_elem.find('fifths')
        mode_elem = key_elem.find('mode')
        fifths = int(fifths_elem.text) if fifths_elem is not None else 0
        mode = mode_elem.text if mode_elem is not None else 'major'
        return {'fifths': fifths, 'mode': mode}

    def extract_time_signature(self) -> Tuple[int, int]:
        time_elem = self.root.find('.//time')
        if time_elem is None:
            return (4, 4)
        beats = time_elem.find('beats')
        beat_type = time_elem.find('beat-type')
        return (int(beats.text) if beats is not None else 4, int(beat_type.text) if beat_type is not None else 4)

    def parse_full_score(self) -> Dict[int, List[Note]]:
        voices = defaultdict(list)
        for part in self.root.findall('.//part'):
            for measure_elem in part.findall('measure'):
                measure_num = int(measure_elem.get('number', 1))
                self._update_divisions(measure_elem)
                current_beat = 0.0
                for note_elem in measure_elem.findall('note'):
                    note = self._parse_note_element(note_elem, measure_num, current_beat)
                    if note:
                        note.beat_position = current_beat
                        voices[note.voice].append(note)
                        if not note.is_chord_tone:
                            current_beat += self._duration_to_beats(note.duration)
        return dict(voices)

    def _update_divisions(self, measure_elem: ET.Element):
        attributes = measure_elem.find('attributes')
        if attributes is not None:
            divisions_elem = attributes.find('divisions')
            if divisions_elem is not None:
                self.divisions = int(divisions_elem.text)

    def _parse_note_element(self, note_elem: ET.Element, measure_num: int, current_beat: float) -> Optional[Note]:
        if note_elem.find('rest') is not None:
            duration = int(note_elem.find('duration').text) if note_elem.find('duration') is not None else 4
            note_type = note_elem.find('type').text if note_elem.find('type') is not None else 'quarter'
            voice = int(note_elem.find('voice').text) if note_elem.find('voice') is not None else 1
            return Note(is_rest=True, duration=duration, note_type=note_type, measure=measure_num, voice=voice,
                        beat_position=current_beat)

        pitch_elem = note_elem.find('pitch')
        if pitch_elem is None:
            return None

        step_text = pitch_elem.find('step').text
        alter = 0
        if len(step_text) > 1:
            base_step = step_text[0]
            accidental = step_text[1:]
            if accidental in ['#', '♯']:
                alter = 1
            elif accidental in ['b', '♭']:
                alter = -1
            elif accidental in ['##', 'x']:
                alter = 2
            elif accidental == 'bb':
                alter = -2
            step = base_step
        else:
            step = step_text
            alter_elem = pitch_elem.find('alter')
            alter = int(alter_elem.text) if alter_elem is not None else 0

        octave = int(pitch_elem.find('octave').text)
        pitch = Pitch(step=step, alter=alter, octave=octave)

        duration = int(note_elem.find('duration').text) if note_elem.find('duration') is not None else 4
        note_type = note_elem.find('type').text if note_elem.find('type') is not None else 'quarter'
        voice = int(note_elem.find('voice').text) if note_elem.find('voice') is not None else 1
        is_chord_tone = note_elem.find('chord') is not None
        is_tied = note_elem.find('.//tied') is not None

        return Note(
            pitch=pitch, duration=duration, note_type=note_type, measure=measure_num,
            voice=voice, beat_position=current_beat, is_chord_tone=is_chord_tone, is_tied=is_tied
        )

    def _duration_to_beats(self, duration: int) -> float:
        return duration / self.divisions
