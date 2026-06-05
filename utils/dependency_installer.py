import sys
import subprocess
import importlib
from core.logger import logger


def ensure_dependency(package_name, import_name=None, version=None):
    """
    确保Python依赖已安装，未安装则自动pip install
    
    Args:
        package_name: pip包名 (如 'openpyxl')
        import_name: 导入时的模块名 (如 'openpyxl'，默认为package_name)
        version: 版本号约束 (如 '>=3.0.0')
    
    Returns:
        bool: 是否成功
    """
    if import_name is None:
        import_name = package_name

    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        pass

    pip_package = package_name
    if version:
        pip_package = f"{package_name}{version}"

    logger.info(f"检测到缺少依赖 {package_name}，正在自动安装...")
    try:
        result = subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', pip_package, '-q'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120
        )
        importlib.import_module(import_name)
        logger.info(f"依赖 {package_name} 安装成功")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"安装依赖 {package_name} 失败: {e}")
        return False
    except subprocess.TimeoutExpired:
        logger.error(f"安装依赖 {package_name} 超时")
        return False
    except ImportError:
        logger.error(f"安装后仍无法导入 {import_name}")
        return False


def ensure_excel_deps():
    """确保Excel导出依赖已安装"""
    return ensure_dependency('openpyxl', 'openpyxl', '>=3.0.0')


def ensure_pdf_deps():
    """确保PDF导出依赖已安装"""
    return ensure_dependency('reportlab', 'reportlab', '>=3.6.0')


def ensure_web_deps():
    """确保Flask Web依赖已安装"""
    return ensure_dependency('flask', 'flask', '>=2.0.0')


def ensure_all_deps():
    """确保所有可选依赖已安装"""
    results = []
    results.append(('Flask', ensure_web_deps()))
    results.append(('openpyxl (Excel)', ensure_excel_deps()))
    results.append(('reportlab (PDF)', ensure_pdf_deps()))
    return results
