# main.py
"""
musictheorybench 项目的命令行入口和示例脚本。
"""
import os
import sys
import json
from collections import defaultdict
from typing import Optional, List, Dict, Any

# 从我们新建的包中导入核心类
from base_validator import CompleteMusicTheoryValidator
from models import Pitch, Interval


# ========== 自定义工具函数 ==========

def custom_json_encoder(obj: Any) -> Any:
    """自定义JSON编码器，处理Pitch和Interval等非原生JSON类型"""
    if isinstance(obj, Pitch):
        return str(obj)
    if isinstance(obj, Interval):
        return {'generic': obj.generic_interval, 'quality': obj.quality, 'dir': obj.direction}
    # 对于其他无法序列化的对象，可以抛出错误或返回其字符串表示
    try:
        return json.JSONEncoder().default(obj)
    except TypeError:
        return str(obj)

# ========== 分析流程函数 ==========

def analyze_musicxml_file(file_path: str, style: Optional[str] = None) -> Dict[str, Any]:
    """使用MusicTheoryBench库分析单个MusicXML文件"""
    try:
        validator = CompleteMusicTheoryValidator(file_path)
        results = validator.evaluate_complete_L0_L1_L2_analysis(style=style)

        results['key_signature'] = validator.key_signature
        results['time_signature'] = validator.time_signature
        results['analysis_metadata'] = {
            'analyzer_version': '1.0.0',
            'analysis_date': '2024-05-21', # 建议使用 datetime.now()
            'file_analyzed': os.path.basename(file_path),
            'style_analyzed': style
        }
        return results
    except Exception as e:
        import traceback
        return {'error': '分析失败', 'details': str(e), 'traceback': traceback.format_exc(), 'status': 'failed'}

def evaluate_multiple_files(file_paths: List[str], style: Optional[str] = None) -> Dict[str, Dict]:
    """批量评估多个MusicXML文件"""
    results = {}
    for file_path in file_paths:
        print(f"\n{'=' * 60}\n分析文件: {os.path.basename(file_path)}\n{'=' * 60}")
        result = analyze_musicxml_file(file_path, style=style)
        results[os.path.basename(file_path)] = result
    return results

def evaluate_files_in_directory(directory_path: str, style: Optional[str] = None) -> Dict[str, Dict]:
    """批量评估文件夹中的所有MusicXML/MXL文件"""
    file_paths = [os.path.join(root, file) for root, _, files in os.walk(directory_path) for file in files if file.lower().endswith(('.xml', '.mxl'))]
    if not file_paths:
        print(f"目录 {directory_path} 中没有找到任何 .xml 或 .mxl 文件。")
        return {}
    return evaluate_multiple_files(file_paths, style=style)

# ========== 调试与报告函数 ==========

def debug_l0_errors_comprehensive(file_path: str, injected_errors_json: str):
    """综合调试L0错误检测，对比注入的错误"""
    print(f"调试文件: {file_path}")
    print("=" * 80)
    validator = CompleteMusicTheoryValidator(file_path)
    validator.print_detailed_l0_errors()
    validator.compare_with_injected_errors(injected_errors_json)
    validator.analyze_specific_error_types(injected_errors_json)

def print_l0_error_summary(file_path: str, save_json_path: Optional[str] = None):
    """打印指定文件的L0错误摘要，并可选择保存为JSON"""
    validator = CompleteMusicTheoryValidator(file_path)
    errors = validator.check_L0_complete()
    errors_sorted = sorted(errors, key=lambda e: (e["location"].get("measure", 0), e["location"].get("voice", 0)))

    print(f"\n=== L0 Error Summary for {os.path.basename(file_path)} ===")
    for idx, err in enumerate(errors_sorted, 1):
        loc = err["location"]
        print(f"{idx:3}. [{err['type']}]  m{loc.get('measure', '?'):>3} v{loc.get('voice', '?'):>2}  - {err['message']}")

    if save_json_path:
        try:
            with open(save_json_path, "w", encoding="utf-8") as fp:
                json.dump(errors_sorted, fp, ensure_ascii=False, indent=2, default=custom_json_encoder)
            print(f"\n详细JSON已保存到: {save_json_path}")
        except Exception as exc:
            print(f"⚠️ 无法写入JSON文件: {exc}")

# ========== 主程序入口 ==========

if __name__ == "__main__":

    # --- 任务1: 批量分析一个目录并汇总结果 ---
    print("\n>>> 任务1: 批量分析目录并汇总...")
    # 请将此路径修改为您自己的目录
    directory_to_scan = r"C:\Users\AOOOOOOO\Desktop\document\Y3S2\RA\evaluatingmusic\single_file_output\batch_output_20250917_225400\corrupted_xml"
    style_to_analyze = "classical"

    if os.path.isdir(directory_to_scan):
        all_results = evaluate_files_in_directory(directory_to_scan, style=style_to_analyze)

        overall_scores = []
        error_totals = defaultdict(int)

        for file_name, result in all_results.items():
            if 'error' in result:
                print(f"❌  {file_name}: 分析失败 - {result['details']}")
                continue

            score = result['summary']['compliance_scores']['overall']
            overall_scores.append(score)
            print(f"✅  {file_name:<40s}  →  Overall Compliance = {score:.2%}")

            all_errs = result.get("L0_errors", []) + result.get("L1_errors", []) + result.get("L2_errors", [])
            for err in all_errs:
                error_totals[err.get("type", "unknown")] += 1

        if overall_scores:
            avg_score = sum(overall_scores) / len(overall_scores)
            print("\n" + "=" * 60)
            print(f"🎯  平均 Overall Compliance ({len(overall_scores)} 个文件): {avg_score:.2%}")
            print("=" * 60)

        if error_totals:
            print("\n=== 所有文件的错误类型总计 ===")
            for etype, cnt in sorted(error_totals.items(), key=lambda x: (-x[1], x[0])):
                print(f"{etype:<35} {cnt}")
    else:
        print(f"警告: 目录不存在, 跳过批量分析任务: {directory_to_scan}")

    # --- 任务2: 对特定文件进行L0错误注入调试 ---
    print("\n\n>>> 任务2: L0错误注入调试...")
    # 请将此路径修改为您的文件
    debug_file_path = r"C:\Users\AOOOOOOO\Desktop\document\Y3S2\RA\evaluatingmusic\error_output\xml_files\variant_001.xml"
    injected_json_data = '''
    [{"error_type": "octave_displacement", "location": {"measure": 1}, "original_content": "B3", "corrupted_content": "B2"},
     {"error_type": "enharmonic_error", "location": {"measure": 2}, "original_content": "Ab", "corrupted_content": "G#"}]
    ''' # 此处为简化版JSON，请使用您完整的JSON数据

    if os.path.exists(debug_file_path):
        # 实际使用时请取消下面的注释
        # debug_l0_errors_comprehensive(debug_file_path, injected_json_data)
        print("调试函数 `debug_l0_errors_comprehensive` 已准备就绪，但默认被注释以避免过长输出。")
        print("如需运行，请在 main.py 的 `if __name__ == '__main__'` 部分取消相关代码的注释。")
    else:
        print(f"警告: 调试文件不存在, 跳过L0调试任务: {debug_file_path}")

    print("\n所有任务执行完毕。")

