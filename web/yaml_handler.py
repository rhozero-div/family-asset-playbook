"""YAML 输入处理 + 调计算引擎。

接收 YAML 字符串,校验后调用 engine.cli._generate_playbook。
以客户代码命名文件: profiles/{000001..999999}.yaml。
"""
from __future__ import annotations

import sys
import tempfile
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from engine.cli import _generate_playbook  # noqa: E402
from tools.validate_collected_profile import _validate  # noqa: E402

_CODE_RE = re.compile(r"^(\d{6})\.yaml$")


def receive_yaml_text(yaml_text: str) -> tuple[bool, str, str]:
    if not yaml_text or not yaml_text.strip():
        return False, "", "YAML 内容为空"
    import yaml
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        return False, "", f"YAML 解析失败: {e}"
    ok, errors = _validate(data if isinstance(data, dict) else {}, Path("<inline>"))
    if not ok:
        return False, "", "; ".join(errors)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_text)
        return True, str(Path(f.name)), ""


def save_yaml_and_generate(
    yaml_text: str, current_year: int, client_code: str = "", lang: str = "zh",
) -> tuple[bool, str, str]:
    """保存 YAML 到 profiles/{code}.yaml, 生成剧本, 同步注册表。

    client_code 为空时自动分配新码。
    Returns: (ok, playbook_md, error_msg)
    """
    ok, tmp_or_err, error_msg = receive_yaml_text(yaml_text)
    if not ok:
        return False, "", error_msg
    tmp_path = Path(tmp_or_err)

    profiles_dir = PROJECT_ROOT / "profiles"
    profiles_dir.mkdir(exist_ok=True)

    ok, code, code_error = ensure_code_is_available(yaml_text, client_code)
    if not ok:
        tmp_path.unlink(missing_ok=True)
        return False, "", code_error

    saved_path = profiles_dir / f"{code}.yaml"
    saved_path.write_text(yaml_text, encoding="utf-8")

    _sync_clients_json(profiles_dir)

    try:
        playbook_md = _generate_playbook(
            profile_path=tmp_path,
            handbook_dir=PROJECT_ROOT / "handbook",
            current_year=current_year,
            lang=lang,
        )
        return True, playbook_md, ""
    except Exception as e:
        return False, "", f"生成剧本失败: {e}"
    finally:
        tmp_path.unlink(missing_ok=True)


def generate_playbook_from_yaml(
    yaml_text: str, current_year: int, lang: str = "zh",
) -> tuple[bool, str, str]:
    """不落盘保存客户资料,仅基于输入 YAML 生成剧本。"""
    ok, tmp_or_err, error_msg = receive_yaml_text(yaml_text)
    if not ok:
        return False, "", error_msg
    tmp_path = Path(tmp_or_err)
    try:
        playbook_md = _generate_playbook(
            profile_path=tmp_path,
            handbook_dir=PROJECT_ROOT / "handbook",
            current_year=current_year,
            lang=lang,
        )
        return True, playbook_md, ""
    except Exception as e:
        return False, "", f"生成剧本失败: {e}"
    finally:
        tmp_path.unlink(missing_ok=True)


def _resolve_code(yaml_text: str, client_code: str, profiles_dir: Path) -> str:
    """确定客户代码: 优先使用传入 code; 其次查找同名已有客户; 最后新分配。"""
    import json, yaml
    name = _family_name(yaml_text)
    clients_path = profiles_dir / "clients.json"
    registry: dict = {}
    if clients_path.exists():
        registry = json.loads(clients_path.read_text(encoding="utf-8"))

    # 优先使用传入 code。新建客户时也允许显式指定未占用的 code。
    if client_code and _CODE_RE.match(f"{client_code}.yaml"):
        return client_code

    # 查找同名客户,复用其 code
    for c, entry in registry.items():
        if entry.get("name") == name and _CODE_RE.match(entry.get("yaml_file", "")):
            return c

    # 新分配
    existing = [int(k) for k in registry.keys() if k.isdigit()]
    return f"{max(existing + [0]) + 1:06d}"


def _family_name(yaml_text: str) -> str:
    import yaml
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return "unknown"
    if not isinstance(data, dict):
        return "unknown"
    family = data.get("family", {})
    if not isinstance(family, dict):
        return "unknown"
    for m in family.get("members", []):
        if isinstance(m, dict) and m.get("role") == "primary_breadwinner":
            return str(m.get("name", "unknown"))
    return "unknown"


def _sync_clients_json(profiles_dir: Path) -> list[dict]:
    """扫描 profiles/{code}.yaml, 更新 clients.json 注册表。"""
    import json, yaml

    clients_path = profiles_dir / "clients.json"
    registry: dict[str, dict] = {}
    if clients_path.exists():
        registry = json.loads(clients_path.read_text(encoding="utf-8"))

    known_codes: set[str] = set()

    for f in sorted(profiles_dir.glob("*.yaml")):
        if f.name in ("clients.json", "sample-wang.yaml"):
            continue
        m = _CODE_RE.match(f.name)
        if not m:
            # 旧版 name-based 文件,尝试迁移
            _migrate_name_file(f, profiles_dir, registry)
            continue
        code = m.group(1)
        known_codes.add(code)
        if code in registry:
            continue
        # 读取 YAML 获取姓名
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            name = _family_name_from_data(data) or f.stem
        except Exception:
            continue
        registry[code] = {
            "name": name,
            "yaml_file": f.name,
            "tags": ["", ""],
            "notes": "",
        }

    # 清理已删除的文件
    for code in list(registry.keys()):
        if code not in known_codes:
            del registry[code]

    clients_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    return list(registry.values())


def _migrate_name_file(f: Path, profiles_dir: Path, registry: dict) -> None:
    """将旧版 name-based YAML 迁移为 code-based。"""
    import json, yaml
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return
        name = _family_name_from_data(data) or f.stem
    except Exception:
        return
    # 检查是否已有该 name 的条目
    for code, entry in registry.items():
        if entry.get("name") == name:
            # 重命名文件
            new_name = f"{code}.yaml"
            f.rename(profiles_dir / new_name)
            entry["yaml_file"] = new_name
            return
    # 无匹配,分配新 code
    existing = [int(k) for k in registry.keys() if k.isdigit()]
    code = f"{max(existing + [0]) + 1:06d}"
    new_name = f"{code}.yaml"
    f.rename(profiles_dir / new_name)
    registry[code] = {
        "name": name,
        "yaml_file": new_name,
        "tags": ["", ""],
        "notes": "",
    }


def _family_name_from_data(data: dict) -> str | None:
    family = data.get("family", {})
    if not isinstance(family, dict):
        return None
    for m in family.get("members", []):
        if isinstance(m, dict) and m.get("role") == "primary_breadwinner":
            return str(m.get("name", "unknown"))
    return None


def read_clients() -> list[dict]:
    """读取客户注册表(每次调用自动同步)。"""
    profiles_dir = PROJECT_ROOT / "profiles"
    profiles_dir.mkdir(exist_ok=True)
    items = _sync_clients_json(profiles_dir)
    # items 不含 code(key 在外层),重新组装
    import json
    clients_path = profiles_dir / "clients.json"
    registry = json.loads(clients_path.read_text(encoding="utf-8"))
    return [{"code": k, **v} for k, v in sorted(registry.items()) if v.get("yaml_file")]


def save_yaml_only(yaml_text: str, client_code: str) -> tuple[bool, str, str]:
    """仅保存 YAML 到 profiles/{code}.yaml, 不生成剧本。

    Returns: (ok, code_or_error, error_msg)
    """
    ok, tmp_or_err, error_msg = receive_yaml_text(yaml_text)
    if not ok:
        return False, "", error_msg

    profiles_dir = PROJECT_ROOT / "profiles"
    profiles_dir.mkdir(exist_ok=True)

    # 确定代码
    code = _resolve_code(yaml_text, client_code, profiles_dir)
    name = _family_name(yaml_text)

    # 查重: 代码已存在且姓名不同 → 拒绝
    clients_path = profiles_dir / "clients.json"
    import json
    registry = {}
    if clients_path.exists():
        registry = json.loads(clients_path.read_text(encoding="utf-8"))
    if code in registry and registry[code].get("name") != name:
        return False, "", f"客户代码 {code} 已被 {registry[code]['name']} 使用"

    saved_path = profiles_dir / f"{code}.yaml"
    saved_path.write_text(yaml_text, encoding="utf-8")
    _sync_clients_json(profiles_dir)
    return True, code, ""


def ensure_code_is_available(yaml_text: str, client_code: str) -> tuple[bool, str, str]:
    """校验解析后的客户代码是否可用于当前 YAML。"""
    profiles_dir = PROJECT_ROOT / "profiles"
    profiles_dir.mkdir(exist_ok=True)
    code = _resolve_code(yaml_text, client_code, profiles_dir)
    name = _family_name(yaml_text)

    clients_path = profiles_dir / "clients.json"
    import json
    registry = {}
    if clients_path.exists():
        registry = json.loads(clients_path.read_text(encoding="utf-8"))

    if code in registry and registry[code].get("name") != name:
        return False, "", f"客户代码 {code} 已被 {registry[code]['name']} 使用"
    return True, code, ""


def next_client_code() -> str:
    """返回下一个可用客户代码。"""
    from pathlib import Path
    profiles_dir = PROJECT_ROOT / "profiles"
    profiles_dir.mkdir(exist_ok=True)
    clients_path = profiles_dir / "clients.json"
    import json
    existing = []
    if clients_path.exists():
        registry = json.loads(clients_path.read_text(encoding="utf-8"))
        existing = [int(k) for k in registry.keys() if k.isdigit()]
    return f"{max(existing + [0]) + 1:06d}"


def update_client(code: str, data: dict) -> None:
    import json
    profiles_dir = PROJECT_ROOT / "profiles"
    clients_path = profiles_dir / "clients.json"
    if not clients_path.exists():
        return
    registry = json.loads(clients_path.read_text(encoding="utf-8"))
    if code not in registry:
        return
    entry = registry[code]
    if "tags" in data:
        entry["tags"] = data["tags"]
    if "notes" in data:
        entry["notes"] = data["notes"]
    clients_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
