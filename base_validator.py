# musictheorybench/validation/base_validator.py
"""
验证器主类，组合所有 Mixins，并负责初始化、执行分析、计算分数和提供调试工具。
"""
import math
import json
from collections import defaultdict
from typing import List, Dict, Optional, Any
from parser import StandardMusicXMLParser
from common_helpers import CommonHelpersMixin
from l0_rules import L0RulesMixin
from l1_rules import L1RulesMixin
from l2_rules import L2RulesMixin


class CompleteMusicTheoryValidator(CommonHelpersMixin, L0RulesMixin, L1RulesMixin, L2RulesMixin):
    """完整的音乐理论验证器，通过继承组合了L0, L1, L2的验证功能"""

    def __init__(self, xml_content: str):
        self.parser = StandardMusicXMLParser(xml_content)
        self.key_signature = self.parser.extract_key_signature()
        self.time_signature = self.parser.extract_time_signature()
        self.voices = self.parser.parse_full_score()
        self._init_error_buckets()

    def _init_error_buckets(self):
        self.error_buckets = {'L0': defaultdict(list), 'L1': defaultdict(list)}

    def _bucket_error(self, err: dict):
        lvl = err.get('level', 'L0')
        self.error_buckets[lvl][err['type']].append(err)

    def evaluate_complete_L0_L1_L2_analysis(self, style: Optional[str] = None) -> Dict[str, any]:
        """执行完整的L0-L1-L2三层分析"""
        results = {
            'L0_errors': [], 'L1_errors': [], 'L2_errors': [],
            'analysis_breakdown': {
                'L0': {}, 'L1': {}, 'L2': {}
            },
            'summary': {}, 'style': style
        }

        print("执行L0层分析...")
        l0_errors = self.check_L0_complete()
        results['L0_errors'] = l0_errors
        results['analysis_breakdown']['L0']['all'] = l0_errors

        print("执行L1层分析...")
        l1_rhythmic_errors = self.check_L1_rhythmic_structure_complete()
        l1_tonal_errors = self.check_L1_tonal_consistency_complete()
        l1_voice_errors = self.check_L1_voice_leading_complete()
        l1_errors = l1_rhythmic_errors + l1_tonal_errors + l1_voice_errors
        results['L1_errors'] = l1_errors
        results['analysis_breakdown']['L1'] = {'rhythmic': l1_rhythmic_errors, 'tonal': l1_tonal_errors,
                                               'voice_leading': l1_voice_errors}

        l2_errors = []
        if style:
            print(f"执行L2层风格分析 ({style})...")
            if style == 'classical':
                l2_errors = self.check_L2_classical_style()
            elif style == 'jazz':
                l2_errors = self.check_L2_jazz_style()
            elif style == 'popular':
                l2_errors = self.check_L2_popular_style()
        results['L2_errors'] = l2_errors
        results['analysis_breakdown']['L2']['style_specific'] = l2_errors

        total_notes = sum(len(notes) for notes in self.voices.values())
        non_rest_notes = sum(1 for notes in self.voices.values() for note in notes if not note.is_rest)
        total_measures = max((note.measure for notes in self.voices.values() for note in notes), default=0)

        results['summary'] = {
            'total_notes': total_notes, 'non_rest_notes': non_rest_notes,
            'total_voices': len(self.voices), 'total_measures': total_measures,
            'error_counts': {
                'L0': len(l0_errors), 'L1': len(l1_errors), 'L2': len(l2_errors),
                'total': len(l0_errors) + len(l1_errors) + len(l2_errors)
            },
            'compliance_scores': {
                'L0': self._calculate_compliance_score(l0_errors, non_rest_notes),
                'L1': self._calculate_compliance_score(l1_errors, non_rest_notes),
                'L2': self._calculate_compliance_score(l2_errors, non_rest_notes) if style else None,
                'overall': self._calculate_overall_compliance_score(results, non_rest_notes)
            }
        }

        for err in l0_errors + l1_errors + l2_errors:
            self._bucket_error(err)

        results['score_breakdown'] = self._score_by_error_type(non_rest_notes)
        return results

    def _score_by_error_type(self, total_notes: int) -> Dict[str, Dict[str, Any]]:
        result = {}
        for level, buckets in self.error_buckets.items():
            result[level] = {}
            for err_type, errs in buckets.items():
                W = sum({3: 0.1, 4: 0.3, 5: 0.5}.get(e.get("severity", 3), 0.1) for e in errs)
                ratio = W / max(total_notes, 1)
                k = 10
                score = 1 - math.log(1 + k * ratio) / math.log(1 + k)
                result[level][err_type] = {"count": len(errs), "score": round(score, 3)}
        return result

    def _calculate_compliance_score(self, errors: List[Dict], total_elements: int) -> float:
        if total_elements == 0: return 1.0
        serious_errors = [e for e in errors if e.get('severity', 3) >= 3]
        if not serious_errors: return 1.0

        weighted_error_count = sum({3: 0.1, 4: 0.3, 5: 0.5}.get(e.get('severity', 3), 0.1) for e in serious_errors)
        error_ratio = weighted_error_count / total_elements
        k = 10
        score = 1 - math.log(1 + k * error_ratio) / math.log(1 + k) if error_ratio > 0 else 1.0
        return max(0.0, min(1.0, score))

    def _calculate_overall_compliance_score(self, results: Dict, total_elements: int) -> float:
        if total_elements == 0: return 1.0
        l0_weight, l1_weight, l2_weight = 0.4, 0.6, 0.0

        l0_score = self._calculate_compliance_score(results['L0_errors'], total_elements)
        l1_score = self._calculate_compliance_score(results['L1_errors'], total_elements)

        if results.get('style') and results['L2_errors']:
            l0_weight, l1_weight, l2_weight = 0.2, 0.6, 0.2
            l2_score = self._calculate_compliance_score(results['L2_errors'], total_elements)
            return (l0_score * l0_weight + l1_score * l1_weight + l2_score * l2_weight)

        return (l0_score * l0_weight + l1_score * l1_weight)

    def print_detailed_l0_errors(self):
        l0_errors = self.check_L0_complete()
        print(f"\n=== 检测到的L0错误详情 (总计: {len(l0_errors)}个) ===")
        l0_errors.sort(key=lambda x: x['location'].get('measure', 0))
        for i, error in enumerate(l0_errors, 1):
            loc = error['location']
            print(
                f"{i:2}. [{error['type']}] 小节{loc.get('measure', '?')} 声部{loc.get('voice', '?')} - {error['message']}")
            if 'pitch' in error: print(f"    音高: {error['pitch']}")
            print(f"    严重程度: {error.get('severity', '?')}\n")

    def compare_with_injected_errors(self, injected_errors_json: str):
        """与注入错误进行详细对比"""

        import json

        # 解析注入错误
        try:
            injected_errors = json.loads(injected_errors_json)
        except:
            print("JSON解析失败")
            return

        # 获取检测到的错误
        detected_errors = self.check_L0_complete()

        print(f"\n=== 错误对比分析 ===")
        print(f"注入错误: {len(injected_errors)}个")
        print(f"检测错误: {len(detected_errors)}个")
        print("-" * 60)

        # 按小节组织注入错误
        injected_by_measure = {}
        for error in injected_errors:
            measure = error['location']['measure']
            if measure not in injected_by_measure:
                injected_by_measure[measure] = []
            injected_by_measure[measure].append(error)

        # 按小节组织检测错误
        detected_by_measure = {}
        for error in detected_errors:
            measure = error['location'].get('measure', 0)
            if measure not in detected_by_measure:
                detected_by_measure[measure] = []
            detected_by_measure[measure].append(error)

        # 逐小节对比
        all_measures = sorted(set(injected_by_measure.keys()) | set(detected_by_measure.keys()))

        print("\n小节对比:")
        print("小节 | 注入 | 检测 | 状态")
        print("-" * 30)

        total_matches = 0
        total_missed = 0
        total_false_positives = 0

        for measure in all_measures:
            injected_count = len(injected_by_measure.get(measure, []))
            detected_count = len(detected_by_measure.get(measure, []))

            if injected_count > 0 and detected_count > 0:
                status = "部分匹配" if injected_count != detected_count else "完全匹配"
                total_matches += min(injected_count, detected_count)
            elif injected_count > 0 and detected_count == 0:
                status = "遗漏"
                total_missed += injected_count
            elif injected_count == 0 and detected_count > 0:
                status = "误报"
                total_false_positives += detected_count
            else:
                status = "正常"

            print(f"{measure:4} | {injected_count:4} | {detected_count:4} | {status}")

        print(f"\n=== 总体统计 ===")
        print(f"匹配的错误: {total_matches}")
        print(f"遗漏的错误: {total_missed}")
        print(f"误报的错误: {total_false_positives}")

        if len(injected_errors) > 0:
            detection_rate = total_matches / len(injected_errors)
            print(f"检测率: {detection_rate:.1%}")

        # 详细分析每个小节
        print(f"\n=== 详细小节分析 ===")

        for measure in sorted(all_measures):
            if measure in injected_by_measure or measure in detected_by_measure:
                print(f"\n小节 {measure}:")

                # 显示注入的错误
                if measure in injected_by_measure:
                    print("  注入的错误:")
                    for error in injected_by_measure[measure]:
                        print(
                            f"    - {error['error_type']}: {error['original_content']} → {error['corrupted_content']}")

                # 显示检测到的错误
                if measure in detected_by_measure:
                    print("  检测到的错误:")
                    for error in detected_by_measure[measure]:
                        error_info = f"{error['type']}"
                        if 'pitch' in error:
                            error_info += f": {error['pitch']}"
                        print(f"    - {error_info}")

    def analyze_specific_error_types(self, injected_errors_json: str):
        """按错误类型进行详细分析"""

        import json

        try:
            injected_errors = json.loads(injected_errors_json)
        except:
            print("JSON解析失败")
            return

        detected_errors = self.check_L0_complete()

        print(f"\n=== 按错误类型分析 ===")

        # 统计注入错误类型
        injected_types = {}
        for error in injected_errors:
            error_type = error['error_type']
            if error_type not in injected_types:
                injected_types[error_type] = []
            injected_types[error_type].append(error)

        # 统计检测错误类型
        detected_types = {}
        for error in detected_errors:
            error_type = error['type']
            if error_type not in detected_types:
                detected_types[error_type] = []
            detected_types[error_type].append(error)

        # 映射关系 (注入类型 -> 检测类型)
        type_mapping = {
            'enharmonic_error': ['enharmonic_error', 'poor_enharmonic_spelling'],
            'octave_displacement': ['octave_displacement', 'extreme_melodic_leap', 'excessive_leap'],
            'pitch_substitution': ['pitch_substitution', 'scale_deviation', 'unjustified_accidental']
        }

        print("\n类型对比:")
        print("注入类型 -> 预期检测类型 | 注入数量 | 检测数量")
        print("-" * 60)

        for injected_type, expected_detected_types in type_mapping.items():
            injected_count = len(injected_types.get(injected_type, []))

            total_detected = 0
            for detected_type in expected_detected_types:
                total_detected += len(detected_types.get(detected_type, []))

            print(f"{injected_type} -> {expected_detected_types}")
            print(f"    注入: {injected_count}, 检测: {total_detected}")

            if injected_count > 0:
                detection_rate = min(total_detected / injected_count, 1.0)
                print(f"    检测率: {detection_rate:.1%}")
            print()
