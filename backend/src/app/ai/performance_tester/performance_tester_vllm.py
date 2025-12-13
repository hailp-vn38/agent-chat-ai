import time
import asyncio
import logging
import statistics
import base64
from typing import Dict
from tabulate import tabulate
from app.ai.utils.vllm import create_instance
from config.settings import load_config


# Đặt mức log toàn cục là WARNING để ẩn log INFO
logging.basicConfig(level=logging.WARNING)

description = "Kiểm thử hiệu năng mô hình nhận dạng thị giác"


class AsyncVisionPerformanceTester:
    def __init__(self):
        self.config = load_config()

        self.test_images = [
            "../../docs/images/demo1.png",
            "../../docs/images/demo2.png",
        ]
        self.test_questions = [
            "Trong bức ảnh này có gì?",
            "Hãy mô tả chi tiết nội dung bức ảnh này",
        ]

        # Tải danh sách hình ảnh kiểm thử
        self.results = {"vllm": {}}

    async def _test_vllm(self, vllm_name: str, config: Dict) -> Dict:
        """Kiểm thử bất đồng bộ hiệu năng của một mô hình thị giác"""
        try:
            # Kiểm tra cấu hình API key
            if "api_key" in config and any(
                x in config["api_key"] for x in ["của bạn", "placeholder", "sk-xxx"]
            ):
                print(f"⏭️  VLLM {vllm_name} chưa cấu hình api_key, bỏ qua")
                return {"name": vllm_name, "type": "vllm", "errors": 1}

            # Lấy loại mô-đun thực tế (tương thích cấu hình cũ)
            module_type = config.get("type", vllm_name)
            vllm = create_instance(module_type, config)

            print(f"🖼️ Kiểm thử VLLM: {vllm_name}")

            # Tạo tất cả tác vụ kiểm thử
            test_tasks = []
            for question in self.test_questions:
                for image in self.test_images:
                    test_tasks.append(
                        self._test_single_vision(vllm_name, vllm, question, image)
                    )

            # Thực thi song song tất cả kiểm thử
            test_results = await asyncio.gather(*test_tasks)

            # Xử lý kết quả
            valid_results = [r for r in test_results if r is not None]
            if not valid_results:
                print(f"⚠️  {vllm_name} không có dữ liệu hợp lệ, có thể cấu hình sai")
                return {"name": vllm_name, "type": "vllm", "errors": 1}

            response_times = [r["response_time"] for r in valid_results]

            # Lọc bỏ dữ liệu bất thường
            mean = statistics.mean(response_times)
            stdev = statistics.stdev(response_times) if len(response_times) > 1 else 0
            filtered_times = [t for t in response_times if t <= mean + 3 * stdev]

            if len(filtered_times) < len(test_tasks) * 0.5:
                print(f"⚠️  {vllm_name} dữ liệu hợp lệ không đủ, có thể mạng không ổn định")
                return {"name": vllm_name, "type": "vllm", "errors": 1}

            return {
                "name": vllm_name,
                "type": "vllm",
                "avg_response": sum(response_times) / len(response_times),
                "std_response": (
                    statistics.stdev(response_times) if len(response_times) > 1 else 0
                ),
                "errors": 0,
            }

        except Exception as e:
            print(f"⚠️ VLLM {vllm_name} kiểm thử thất bại: {str(e)}")
            return {"name": vllm_name, "type": "vllm", "errors": 1}

    async def _test_single_vision(
        self, vllm_name: str, vllm, question: str, image: str
    ) -> Dict:
        """Kiểm thử hiệu năng cho một câu hỏi thị giác"""
        try:
            print(f"📝 {vllm_name} bắt đầu kiểm thử: {question[:20]}...")
            start_time = time.time()

            # Đọc ảnh và chuyển sang base64
            with open(image, "rb") as image_file:
                image_data = image_file.read()
                image_base64 = base64.b64encode(image_data).decode("utf-8")

            # Gửi yêu cầu và lấy phản hồi
            response = vllm.response(question, image_base64)
            response_time = time.time() - start_time
            print(f"✓ {vllm_name} hoàn thành phản hồi: {response_time:.3f}s")

            return {
                "name": vllm_name,
                "type": "vllm",
                "response_time": response_time,
            }
        except Exception as e:
            print(f"⚠️ {vllm_name} kiểm thử thất bại: {str(e)}")
            return None

    def _print_results(self):
        """In kết quả kiểm thử"""
        vllm_table = []
        for name, data in self.results["vllm"].items():
            if data["errors"] == 0:
                stability = data["std_response"] / data["avg_response"]
                vllm_table.append(
                    [
                        name,
                        f"{data['avg_response']:.3f} giây",
                        f"{stability:.3f}",
                    ]
                )

        if vllm_table:
            print("\nBảng xếp hạng hiệu năng mô hình thị giác:\n")
            print(
                tabulate(
                    vllm_table,
                    headers=["Tên mô hình", "Thời gian phản hồi", "Độ ổn định"],
                    tablefmt="github",
                    colalign=("left", "right", "right"),
                    disable_numparse=True,
                )
            )
        else:
            print("\n⚠️ Không có mô hình thị giác khả dụng để kiểm thử.")

    async def run(self):
        """Thực thi kiểm thử bất đồng bộ toàn diện"""
        print("🔍 Bắt đầu tìm kiếm các mô hình thị giác khả dụng...")

        if not self.test_images:
            print(f"\n⚠️  Không có tệp ảnh trong đường dẫn {self.image_root}, không thể kiểm thử")
            return

        # Tạo toàn bộ tác vụ kiểm thử
        all_tasks = []

        # Tác vụ kiểm thử VLLM
        if self.config.get("VLLM") is not None:
            for vllm_name, config in self.config.get("VLLM", {}).items():
                if "api_key" in config and any(
                    x in config["api_key"] for x in ["của bạn", "placeholder", "sk-xxx"]
                ):
                    print(f"⏭️  VLLM {vllm_name} chưa cấu hình api_key, bỏ qua")
                    continue
                print(f"🖼️ Thêm tác vụ kiểm thử VLLM: {vllm_name}")
                all_tasks.append(self._test_vllm(vllm_name, config))

        print(f"\n✅ Tìm thấy {len(all_tasks)} mô hình thị giác khả dụng")
        print(f"✅ Sử dụng {len(self.test_images)} ảnh kiểm thử")
        print(f"✅ Sử dụng {len(self.test_questions)} câu hỏi kiểm thử")
        print("\n⏳ Bắt đầu kiểm thử song song tất cả mô hình...\n")

        # Thực thi song song toàn bộ tác vụ kiểm thử
        all_results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Xử lý kết quả
        for result in all_results:
            if isinstance(result, dict) and result["errors"] == 0:
                self.results["vllm"][result["name"]] = result

        # In kết quả
        print("\n📊 Tạo báo cáo kiểm thử...")
        self._print_results()


async def main():
    tester = AsyncVisionPerformanceTester()
    await tester.run()


if __name__ == "__main__":
    asyncio.run(main())
