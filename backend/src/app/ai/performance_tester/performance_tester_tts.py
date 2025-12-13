import asyncio
import logging
import os
import sys
import time
from typing import Dict
import yaml
from tabulate import tabulate

# Thêm thư mục src vào sys.path để import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))


# Đảm bảo import create_tts_instance từ core.utils.tts
from app.ai.utils.tts import create_instance as create_tts_instance
from app.ai.utils.paths import get_data_dir


# Đặt mức log toàn cục là WARNING
logging.basicConfig(level=logging.WARNING)

description = "Kiểm thử hiệu năng tổng hợp giọng nói không dạng luồng"


class TTSPerformanceTester:
    def __init__(self):
        self.config = self._load_config_from_data_dir()
        self.test_sentences = [
            "Năm Vĩnh Hòa thứ chín, tiết lập xuân năm Quý Sửu; how are you today?",
            # "Con người sống cùng nhau trong cõi đời, có người giữ lại những cảm xúc trong lòng, thổ lộ trong một căn phòng; cũng có người gửi gắm tâm tư, vượt ra ngoài hình hài. Tuy ham muốn và lựa chọn mỗi người mỗi khác, sự tĩnh và động cũng chẳng giống nhau,",
            # "Mỗi khi đọc lại nguyên do cảm hứng của người xưa, như gặp được tri kỷ, chẳng bao giờ không xúc động trước trang văn mà than thở, không thể giãi bày hết trong lòng. Mới biết chuyện sống chết là hư ảo, xem Tề Bành Thương là điều sai lầm.",
        ]
        self.results = {}

        # Nhật ký debug
        print(f"[DEBUG] Cấu hình TTS đã nạp: {self.config.get('TTS', {})}")

    def _load_config_from_data_dir(self) -> Dict:
        """Tải cấu hình từ tất cả tệp .config.yaml trong thư mục data"""
        config = {"TTS": {}}
        # Lấy đường dẫn tương đối từ script hiện tại đến thư mục src/data

        data_dir = get_data_dir()
        print(f"[DEBUG] Quét thư mục cấu hình: {data_dir}")

        for root, _, files in os.walk(data_dir):
            for file in files:
                if file.endswith(".config.yaml") or file.endswith(".config.yml"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            file_config = yaml.safe_load(f)
                            # Tương thích khóa TTS/tts không phân biệt chữ hoa
                            tts_config = file_config.get("TTS") or file_config.get(
                                "tts"
                            )
                            if tts_config:
                                config["TTS"].update(tts_config)
                                print(
                                    f"[DEBUG] Đã tải cấu hình TTS từ {file_path} thành công"
                                )
                    except Exception as e:
                        print(f"⚠️ Không thể tải tệp cấu hình {file_path}: {str(e)}")
        return config

    async def _test_tts(self, tts_name: str, config: Dict) -> Dict:
        """Kiểm thử hiệu năng của một mô-đun TTS"""
        try:
            # Kiểm tra tính hợp lệ của cấu hình
            token_fields = ["access_token", "api_key", "token"]
            if any(
                field in config
                and str(config[field]).lower()
                in ["你的", "placeholder", "none", "null", ""]
                for field in token_fields
            ):
                print(f"⚠️ TTS {tts_name} chưa có access_token/api_key hợp lệ, bỏ qua")
                return {
                    "name": tts_name,
                    "type": "tts",
                    "errors": 1,
                    "error_type": "Lỗi cấu hình",
                }

            module_type = config.get("type", tts_name)
            tts = create_tts_instance(module_type, config, delete_audio_file=True)

            print(f" Kiểm thử TTS: {tts_name}")

            # Kiểm thử kết nối
            tmp_file = tts.generate_filename()
            result = await tts.text_to_speak("Kiểm thử kết nối", tmp_file)

            if not tmp_file or not os.path.exists(tmp_file):
                print(f" {tts_name} kết nối thất bại")
                return {
                    "name": tts_name,
                    "type": "tts",
                    "errors": 1,
                    "error_type": "Lỗi mạng",
                }

            total_time = 0
            test_count = len(self.test_sentences[:2])

            for i, sentence in enumerate(self.test_sentences[:2], 1):
                start = time.time()
                tmp_file = tts.generate_filename()
                await tts.text_to_speak(sentence, tmp_file)
                duration = time.time() - start
                total_time += duration

                if tmp_file and os.path.exists(tmp_file):
                    print(f" {tts_name} [{i}/{test_count}] thời gian: {duration:.2f}s")
                else:
                    print(f" {tts_name} [{i}/{test_count}] kiểm thử thất bại")
                    return {
                        "name": tts_name,
                        "type": "tts",
                        "errors": 1,
                        "error_type": "Lỗi mạng",
                    }

            return {
                "name": tts_name,
                "type": "tts",
                "avg_time": total_time / test_count,
                "success_rate": f"{test_count}/{test_count}",
                "errors": 0,
            }

        except Exception as e:
            error_msg = str(e).lower()
            if "502" in error_msg or "bad gateway" in error_msg:
                error_type = "Lỗi mạng 502"
            elif "timeout" in error_msg:
                error_type = "Kết nối quá thời gian"
            else:
                error_type = "Lỗi mạng"
            print(f"⚠️ {tts_name} kiểm thử thất bại: {str(e)}")
            return {
                "name": tts_name,
                "type": "tts",
                "errors": 1,
                "error_type": error_type,
            }

    def _print_results(self):
        """In kết quả kiểm thử"""
        print("\n" + "=" * 50)
        print("Kết quả kiểm thử hiệu năng TTS")
        print("=" * 50)

        if not self.results:
            print("Không có kết quả kiểm thử TTS hợp lệ")
            return

        headers = [
            "Mô-đun TTS",
            "Thời gian trung bình (s)",
            "Tỉ lệ thành công",
            "Trạng thái",
        ]
        table_data = []

        # Thu thập và phân loại dữ liệu
        valid_results = []
        error_results = []

        for name, data in self.results.items():
            if data["errors"] == 0:
                # Kết quả hợp lệ
                avg_time = f"{data['avg_time']:.3f}"
                success_rate = data.get("success_rate", "N/A")
                status = "✅ Bình thường"

                # Lưu giá trị phục vụ việc sắp xếp
                valid_results.append(
                    {
                        "name": name,
                        "avg_time": avg_time,
                        "success_rate": success_rate,
                        "status": status,
                        "sort_key": data["avg_time"],
                    }
                )
            else:
                # Kết quả lỗi
                avg_time = "-"
                success_rate = "0/N"

                # Lấy loại lỗi cụ thể
                error_type = data.get("error_type", "Lỗi mạng")
                status = f"❌ {error_type}"

                error_results.append([name, avg_time, success_rate, status])

        # Sắp xếp theo thời gian trung bình tăng dần (từ nhanh tới chậm)
        valid_results.sort(key=lambda x: x["sort_key"])

        # Đưa kết quả hợp lệ đã sắp xếp vào bảng
        for result in valid_results:
            table_data.append(
                [
                    result["name"],
                    result["avg_time"],
                    result["success_rate"],
                    result["status"],
                ]
            )

        # Thêm các kết quả lỗi vào cuối bảng
        table_data.extend(error_results)

        print(
            tabulate(
                table_data,
                headers=headers,
                tablefmt="grid",
                colalign=("left", "right", "right", "left"),
            )
        )
        print("\nGhi chú kiểm thử:")
        print("- Kiểm soát thời gian chờ: mỗi yêu cầu chờ tối đa 10 giây")
        print("- Xử lý lỗi: lỗi kết nối và quá thời gian được xem là lỗi mạng")
        print(
            "- Tỉ lệ thành công: số tệp nhận dạng thành công / tổng số tệp thử nghiệm"
        )
        print(
            "- Quy tắc sắp xếp: thời gian trung bình từ nhanh đến chậm, mô-đun lỗi ở cuối"
        )
        print("\nKiểm thử hoàn tất!")

    async def run(self):
        """Thực thi kiểm thử"""
        print("Bắt đầu lọc các module TTS khả dụng...")
        if not self.config.get("TTS"):
            print("Không tìm thấy module TTS trong cấu hình")
            return

        tasks = []
        for tts_name, config in self.config.get("TTS", {}).items():
            # Kiểm tra tính hợp lệ của cấu hình
            token_fields = ["access_token", "api_key", "token"]
            if any(
                field in config
                and str(config[field]).lower()
                in ["你的", "placeholder", "none", "null", ""]
                for field in token_fields
            ):
                print(f"TTS {tts_name} chưa có access_token/api_key hợp lệ, bỏ qua")
                continue

            print(f"Thêm tác vụ kiểm tra TTS: {tts_name}")
            tasks.append(self._test_tts(tts_name, config))

        if not tasks:
            print("Không có module TTS nào để kiểm tra.")
            return

        print(f"\nTìm thấy {len(tasks)} module TTS khả dụng")
        print("\nBắt đầu kiểm tra song song tất cả module TTS...")

        # Thực thi kiểm thử song song
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Lưu lại toàn bộ kết quả, bao gồm lỗi
        for result in results:
            if isinstance(result, dict) and result.get("type") == "tts":
                self.results[result["name"]] = result

        # In kết quả
        self._print_results()


# Dành cho nhu cầu gọi từ performance_tester.py
async def main():
    tester = TTSPerformanceTester()
    await tester.run()


if __name__ == "__main__":
    asyncio.run(main())
