"""
Performance Tester - Test Agent Module Initialization

Kiểm tra xem agent module có khởi tạo đúng hay không
Flow:
1. Init all modules từ selected_module - log các module đã tạo
2. Init bằng initialize_modules_by_agent
"""

import asyncio
import logging
import os
import sys
import yaml
from typing import Dict, Any

# Thêm src directory vào sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from tabulate import tabulate
from app.ai.utils.paths import get_data_dir
from src.app.ai.module_factory import (
    initialize_modules_by_selected_module,
    initialize_modules_by_agent,
)
from app.core.logger import setup_logging

# Đặt mức log toàn cục là WARNING
logging.basicConfig(level=logging.WARNING)

TAG = "PerformanceAgentASR"
logger = setup_logging()

description = "Kiểm tra khởi tạo module từ agent_config"


class AgentModulePerformanceTester:
    def __init__(self, agent_config: Dict[str, Any]):
        self.config = self._load_config_from_data_dir()
        self.agent_config = agent_config
        self.results = {
            "selected_module": {"modules": {}, "count": 0},
            "by_agent": {"modules": {}, "count": 0},
            "comparison": {},
            "errors": [],
        }

        print(f"[DEBUG] Agent config keys: {list(self.agent_config.keys())}")
        print(
            f"[DEBUG] Config modules: {list(self.config.get('selected_module', {}).keys())}"
        )

    def _load_config_from_data_dir(self) -> Dict[str, Any]:
        """Tải cấu hình từ .config.yml trong thư mục data"""
        config = {}
        data_dir = get_data_dir()
        print(f"[DEBUG] Quét thư mục cấu hình: {data_dir}")

        for root, _, files in os.walk(data_dir):
            for file in files:
                if file.endswith(".config.yaml") or file.endswith(".config.yml"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            file_config = yaml.safe_load(f)
                            if file_config:
                                config.update(file_config)
                                print(
                                    f"[DEBUG] Đã tải cấu hình từ {file_path} thành công"
                                )
                    except Exception as e:
                        self.results["errors"].append(
                            f"Không thể tải tệp cấu hình {file_path}: {str(e)}"
                        )
                        print(f"⚠️ Lỗi tải cấu hình: {str(e)}")
        return config

    def _print_results(self):
        """In kết quả kiểm tra"""
        print("\n" + "=" * 80)
        print("🔍 Kết quả kiểm tra khởi tạo Agent Module")
        print("=" * 80)

        # Agent config info
        print("\n📋 Thông tin Agent:")
        agent_info = [
            ["Agent Code", self.agent_config.get("agent_code", "N/A")],
            ["Agent Name", self.agent_config.get("agent_name", "N/A")],
            ["Language", self.agent_config.get("language", "N/A")],
        ]
        print(tabulate(agent_info, tablefmt="grid"))

        # FLOW 1: Init by selected_module
        print("\n" + "-" * 80)
        print("🔹 FLOW 1: Khởi tạo từ SELECTED_MODULE")
        print("-" * 80)
        if self.results["selected_module"]["modules"]:
            selected_results = []
            for module_name, info in self.results["selected_module"]["modules"].items():
                selected_results.append(
                    [module_name.upper(), "✅", info.get("config_name", "-")]
                )
            print(
                tabulate(
                    selected_results,
                    headers=["Module", "Status", "Config Used"],
                    tablefmt="grid",
                )
            )
            print(f"\nTổng module khởi tạo: {self.results['selected_module']['count']}")
        else:
            print("  ⏭️ Không có module nào từ selected_module")

        # FLOW 2: Init by agent
        print("\n" + "-" * 80)
        print("🔹 FLOW 2: Khởi tạo từ AGENT CONFIG (agent khác selected_module)")
        print("-" * 80)
        if self.results["by_agent"]["modules"]:
            agent_results = []
            for module_name, info in self.results["by_agent"]["modules"].items():
                agent_results.append(
                    [module_name.upper(), "✅", info.get("config_name", "-")]
                )
            print(
                tabulate(
                    agent_results,
                    headers=["Module", "Status", "Config Used"],
                    tablefmt="grid",
                )
            )
            print(f"\nTổng module khởi tạo: {self.results['by_agent']['count']}")
        else:
            print("  ⏭️ Không có module nào được khởi tạo (agent giống selected_module)")

        # Comparison
        print("\n" + "-" * 80)
        print("📊 SO SÁNH CẤU HÌNH")
        print("-" * 80)
        modules_to_compare = ["ASR", "TTS", "VAD", "LLM", "Memory", "Intent"]
        comparison = []

        for module in modules_to_compare:
            agent_value = self.agent_config.get(module, "-")
            selected_value = self.config.get("selected_module", {}).get(module, "-")
            is_different = "✅ Khác" if agent_value != selected_value else "❌ Giống"

            comparison.append(
                [
                    module,
                    agent_value,
                    selected_value,
                    is_different,
                ]
            )

        print(
            tabulate(
                comparison,
                headers=["Module", "Agent", "Selected", "Status"],
                tablefmt="grid",
            )
        )

        # Errors
        if self.results["errors"]:
            print("\n❌ Lỗi:")
            for error in self.results["errors"]:
                print(f"  - {error}")

        print("\n" + "=" * 80)

    async def run(self):
        """Chạy kiểm tra khởi tạo module"""
        print("🚀 Bắt đầu kiểm tra khởi tạo Agent Module...\n")

        # Kiểm tra config
        if not self.config:
            error_msg = "❌ Không tải được cấu hình từ .config.yml"
            print(error_msg)
            self.results["errors"].append(error_msg)
            self._print_results()
            return

        try:
            # FLOW 1: Init by selected_module
            print("⏳ [FLOW 1] Khởi tạo tất cả module từ selected_module...")
            selected_modules = initialize_modules_by_selected_module(
                logger_instance=logger,
                config=self.config,
            )

            self.results["selected_module"]["count"] = len(selected_modules)
            for module_name, module_instance in selected_modules.items():
                config_name = self.config.get("selected_module", {}).get(
                    module_name.upper(), "N/A"
                )
                self.results["selected_module"]["modules"][module_name] = {
                    "config_name": config_name,
                    "instance_type": type(module_instance).__name__,
                }
                print(f"  ✅ {module_name.upper()}: {config_name}")

            # FLOW 2: Init by agent
            print("\n⏳ [FLOW 2] Khởi tạo module từ agent config...")
            agent_modules = initialize_modules_by_agent(
                logger=logger,
                config=self.config,
                agent=self.agent_config,
            )

            self.results["by_agent"]["count"] = len(agent_modules)
            for module_name, module_instance in agent_modules.items():
                config_name = self.agent_config.get(module_name.upper(), "N/A")
                self.results["by_agent"]["modules"][module_name] = {
                    "config_name": config_name,
                    "instance_type": type(module_instance).__name__,
                }
                print(f"  ✅ {module_name.upper()}: {config_name}")

            print("\n✅ Khởi tạo hoàn tất!")

        except Exception as e:
            error_msg = f"Lỗi khi khởi tạo module: {str(e)}"
            print(f"❌ {error_msg}")
            self.results["errors"].append(error_msg)
            import traceback

            traceback.print_exc()

        # In kết quả
        self._print_results()


async def main(agent_config: Dict[str, Any]):
    """Main entry point"""
    tester = AgentModulePerformanceTester(agent_config)
    await tester.run()


if __name__ == "__main__":
    agent_config = {
        "id": "019a2f78-c4be-7ef9-afd3-904ba1e49a46",
        "template_id": "019a3ea0-0768-7b2a-bab1-d39ee8d6b576",
        "agent_code": "Thầy Hà",
        "agent_name": "Thầy giáo Tiếng Anh",
        "lang_code": "vi",
        "language": "Tiếng việt",
        "ASR": "VietNamASRLocal",
        "VAD": "SileroVAD",
        "LLM": "GPT5miniLLM",
        "TTS": "MinhEdgeTTS",
        "Memory": "nomem",
        "Intent": "function_call",
        "prompt": "Bạn là {{agent_code}}, một giáo viên tiếng anh. Bạn sẻ chỉ cho người dùng các học tiếng anh",
        "voiceprint": None,
        "summaryMemory": "tóm tắt ngắn gọn",
        "mcp_endpoint": None,
        "chat_history_conf": 0,
    }

    asyncio.run(main(agent_config))
