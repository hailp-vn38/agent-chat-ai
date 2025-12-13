import asyncio
import logging
import os
import sys
import time
import concurrent.futures
from typing import Dict, Optional

# Thêm src directory vào sys.path để import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from tabulate import tabulate
from app.ai.utils.paths import get_data_dir

from app.ai.utils.asr import create_instance as create_stt_instance

# Đặt mức log toàn cục là WARNING để hạn chế log INFO
logging.basicConfig(level=logging.WARNING)

description = "Bài kiểm tra hiệu năng mô hình nhận dạng giọng nói"


class ASRPerformanceTester:
    def __init__(self):
        self.config = self._load_config_from_data_dir()
        self.test_wav_list = self._load_test_wav_files()
        self.results = {"stt": {}}

        # Nhật ký debug
        print(f"[DEBUG] Cấu hình ASR đã nạp: {self.config.get('ASR', {})}")
        print(f"[DEBUG] Số lượng tệp âm thanh: {len(self.test_wav_list)}")

    def _load_config_from_data_dir(self) -> Dict:
        """Tải cấu hình từ tất cả tệp .config.yaml trong thư mục data"""
        config = {"ASR": {}}
        data_dir = get_data_dir()
        print(f"[DEBUG] Quét thư mục cấu hình: {data_dir}")

        for root, _, files in os.walk(data_dir):
            for file in files:
                if file.endswith(".config.yaml") or file.endswith(".config.yml"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            import yaml

                            file_config = yaml.safe_load(f)
                            # Tương thích khóa ASR/asr không phân biệt chữ hoa
                            asr_config = file_config.get("ASR") or file_config.get(
                                "asr"
                            )
                            if asr_config:
                                config["ASR"].update(asr_config)
                                print(
                                    f"[DEBUG] Đã tải cấu hình ASR từ {file_path} thành công"
                                )
                    except Exception as e:
                        print(f" Không thể tải tệp cấu hình {file_path}: {str(e)}")
        return config

    def _load_test_wav_files(self) -> list:
        """Tải các tệp âm thanh kiểm thử từ src/app/config/audio-test"""
        # Lấy đường dẫn tương đối từ script hiện tại đến thư mục src/app/config/audio-test
        script_dir = os.path.dirname(os.path.abspath(__file__))
        wav_root = os.path.join(script_dir, "..", "..", "config", "audio-test")
        wav_root = os.path.abspath(wav_root)
        print(f"[DEBUG] Thư mục tệp âm thanh: {wav_root}")
        test_wav_list = []

        if os.path.exists(wav_root):
            file_list = os.listdir(wav_root)
            print(f"[DEBUG] Các tệp âm thanh tìm thấy: {file_list}")
            for file_name in file_list:
                file_path = os.path.join(wav_root, file_name)
                # Kiểm tra xem có phải file và có phần mở rộng audio hợp lệ
                if os.path.isfile(file_path) and file_name.lower().endswith(
                    (".wav", ".mp3", ".pcm", ".opus")
                ):
                    try:
                        file_size = os.path.getsize(file_path)
                        print(
                            f"[DEBUG] Tệp {file_name} - Kích thước: {file_size / 1024:.1f}KB"
                        )
                        with open(file_path, "rb") as f:
                            test_wav_list.append(f.read())
                    except Exception as e:
                        print(f"[DEBUG] Lỗi đọc tệp {file_name}: {e}")
        else:
            print(f" Thư mục không tồn tại: {wav_root}")
        return test_wav_list

    async def _test_single_audio(
        self, stt_name: str, stt, audio_data: bytes
    ) -> Optional[float]:
        """Đo hiệu năng với một tệp âm thanh"""
        try:
            start_time = time.time()
            text, _ = await stt.speech_to_text([audio_data], "1", stt.audio_format)
            if text is None:
                return None

            duration = time.time() - start_time

            # Kiểm tra trường hợp thời gian 0.000s bất thường
            if abs(duration) < 0.001:  # nhỏ hơn 1 mili giây xem là bất thường
                print(
                    f"{stt_name} phát hiện thời gian bất thường: {duration:.6f}s (xem là lỗi)"
                )
                return None

            return duration
        except Exception as e:
            error_msg = str(e).lower()
            if "502" in error_msg or "bad gateway" in error_msg:
                print(f"{stt_name} gặp lỗi 502")
                return None
            return None

    async def _test_stt_with_timeout(self, stt_name: str, config: Dict) -> Dict:
        """Kiểm tra bất đồng bộ hiệu năng từng STT với cơ chế timeout"""
        try:
            # Kiểm tra tính hợp lệ của cấu hình
            token_fields = ["access_token", "api_key", "token"]
            if any(
                field in config
                and str(config[field]).lower()
                in ["你的", "placeholder", "none", "null", ""]
                for field in token_fields
            ):
                print(f"  STT {stt_name} chưa có access_token/api_key hợp lệ, bỏ qua")
                return {
                    "name": stt_name,
                    "type": "stt",
                    "errors": 1,
                    "error_type": "Lỗi cấu hình",
                }

            module_type = config.get("type", stt_name)
            stt = create_stt_instance(module_type, config, delete_audio_file=True)
            stt.audio_format = "pcm"

            print(f" Kiểm tra STT: {stt_name}")

            # Dùng thread pool kèm kiểm soát timeout
            loop = asyncio.get_event_loop()

            # Kiểm tra tệp âm thanh đầu tiên để thử kết nối
            try:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        lambda: asyncio.run(
                            self._test_single_audio(
                                stt_name, stt, self.test_wav_list[0]
                            )
                        )
                    )
                    first_result = await asyncio.wait_for(
                        asyncio.wrap_future(future), timeout=10.0
                    )

                    if first_result is None:
                        print(f" {stt_name} kết nối thất bại")
                        return {
                            "name": stt_name,
                            "type": "stt",
                            "errors": 1,
                            "error_type": "Lỗi mạng",
                        }
            except asyncio.TimeoutError:
                print(f" {stt_name} kết nối quá thời gian (10 giây), bỏ qua")
                return {
                    "name": stt_name,
                    "type": "stt",
                    "errors": 1,
                    "error_type": "Kết nối quá thời gian",
                }
            except Exception as e:
                error_msg = str(e).lower()
                if "502" in error_msg or "bad gateway" in error_msg:
                    print(f" {stt_name} gặp lỗi 502, bỏ qua")
                    return {
                        "name": stt_name,
                        "type": "stt",
                        "errors": 1,
                        "error_type": "Lỗi mạng 502",
                    }
                print(f" {stt_name} gặp lỗi kết nối: {str(e)}")
                return {
                    "name": stt_name,
                    "type": "stt",
                    "errors": 1,
                    "error_type": "Lỗi mạng",
                }

                # Kiểm tra toàn bộ với timeout
            total_time = 0
            valid_tests = 0
            test_count = len(self.test_wav_list)

            for i, audio_data in enumerate(self.test_wav_list, 1):
                try:
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            lambda: asyncio.run(
                                self._test_single_audio(stt_name, stt, audio_data)
                            )
                        )
                        duration = await asyncio.wait_for(
                            asyncio.wrap_future(future), timeout=10.0
                        )

                        if duration is not None and duration > 0.001:
                            total_time += duration
                            valid_tests += 1
                            print(
                                f" {stt_name} [{i}/{test_count}] thời gian: {duration:.2f}s"
                            )
                        else:
                            print(
                                f" {stt_name} [{i}/{test_count}] kiểm tra thất bại (bao gồm 0.000s bất thường)"
                            )

                except asyncio.TimeoutError:
                    print(
                        f" {stt_name} [{i}/{test_count}] quá thời gian (10 giây), bỏ qua"
                    )
                    continue
                except Exception as e:
                    error_msg = str(e).lower()
                    if "502" in error_msg or "bad gateway" in error_msg:
                        print(f" {stt_name} [{i}/{test_count}] lỗi 502, bỏ qua")
                        return {
                            "name": stt_name,
                            "type": "stt",
                            "errors": 1,
                            "error_type": "Lỗi mạng 502",
                        }
                    print(f" {stt_name} [{i}/{test_count}] ngoại lệ: {str(e)}")
                    continue
            # Kiểm tra số lượng lần thử hợp lệ
            if valid_tests < test_count * 0.3:  # Tối thiểu 30% tỉ lệ thành công
                print(
                    f" {stt_name} số lần thử thành công quá ít ({valid_tests}/{test_count}), có thể mạng không ổn định"
                )
                return {
                    "name": stt_name,
                    "type": "stt",
                    "errors": 1,
                    "error_type": "Lỗi mạng",
                }

            if valid_tests == 0:
                return {
                    "name": stt_name,
                    "type": "stt",
                    "errors": 1,
                    "error_type": "Lỗi mạng",
                }

            avg_time = total_time / valid_tests
            return {
                "name": stt_name,
                "type": "stt",
                "avg_time": avg_time,
                "success_rate": f"{valid_tests}/{test_count}",
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
            print(f"⚠️ {stt_name} kiểm tra thất bại: {str(e)}")
            return {
                "name": stt_name,
                "type": "stt",
                "errors": 1,
                "error_type": error_type,
            }

    def _print_results(self):
        """In kết quả kiểm tra theo thứ tự thời gian phản hồi"""
        print("\n" + "=" * 50)
        print("Kết quả kiểm tra hiệu năng ASR")
        print("=" * 50)

        if not self.results.get("stt"):
            print("Không có kết quả kiểm tra nào khả dụng")
            return

        headers = [
            "Tên mô hình",
            "Thời gian trung bình(s)",
            "Tỉ lệ thành công",
            "Trạng thái",
        ]
        table_data = []

        # Thu thập và phân loại mọi dữ liệu
        valid_results = []
        error_results = []

        for name, data in self.results["stt"].items():
            if data["errors"] == 0:
                # Kết quả hợp lệ
                avg_time = f"{data['avg_time']:.3f}"
                success_rate = data.get("success_rate", "N/A")
                status = "✅ Bình thường"

                # Lưu giá trị phục vụ việc sắp xếp
                sort_key = data["avg_time"]

                valid_results.append(
                    {
                        "name": name,
                        "avg_time": avg_time,
                        "success_rate": success_rate,
                        "status": status,
                        "sort_key": sort_key,
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

        # Sắp xếp theo thời gian phản hồi tăng dần (từ nhanh tới chậm)
        valid_results.sort(key=lambda x: x["sort_key"])

        # Chuyển kết quả hợp lệ đã sắp xếp sang dữ liệu bảng
        for result in valid_results:
            table_data.append(
                [
                    result["name"],
                    result["avg_time"],
                    result["success_rate"],
                    result["status"],
                ]
            )

        # Thêm các bản ghi lỗi vào cuối bảng
        table_data.extend(error_results)

        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        print("\nGhi chú kiểm thử:")
        print("- Kiểm soát timeout: tối đa 10 giây cho mỗi tệp âm thanh")
        print(
            "- Xử lý lỗi: tự động bỏ qua mô hình gặp lỗi 502, timeout hoặc sự cố mạng"
        )
        print(
            "- Tỉ lệ thành công: số tệp nhận dạng thành công / tổng số tệp thử nghiệm"
        )
        print(
            "- Quy tắc sắp xếp: thời gian trung bình từ nhanh đến chậm, mô hình lỗi ở cuối"
        )
        print("\nKiểm thử hoàn tất!")

    async def run(self):
        """Chạy toàn bộ bài kiểm tra bất đồng bộ"""
        print("Bắt đầu lọc các module ASR khả dụng...")

        # Kiểm tra xem có file âm thanh test không
        if not self.test_wav_list:
            print(
                "❌ Không tìm thấy tệp âm thanh thử nghiệm trong thư mục src/app/config/audio-test"
            )
            print(
                "   Vui lòng đặt file .wav/.mp3/.pcm/.opus vào thư mục src/app/config/audio-test"
            )
            return

        if not self.config.get("ASR"):
            print("Không tìm thấy module ASR trong cấu hình")
            return

        all_tasks = []
        for stt_name, config in self.config["ASR"].items():
            # Kiểm tra tính hợp lệ của cấu hình
            token_fields = ["access_token", "api_key", "token"]
            if any(
                field in config
                and str(config[field]).lower()
                in ["你的", "placeholder", "none", "null", ""]
                for field in token_fields
            ):
                print(f"ASR {stt_name} chưa có access_token/api_key hợp lệ, bỏ qua")
                continue

            print(f"Thêm tác vụ kiểm tra ASR: {stt_name}")
            all_tasks.append(self._test_stt_with_timeout(stt_name, config))

        if not all_tasks:
            print("Không có module ASR nào để kiểm tra.")
            return

        print(f"\nTìm thấy {len(all_tasks)} module ASR khả dụng")
        print("\nBắt đầu kiểm tra song song tất cả module ASR...")
        all_results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Xử lý kết quả
        for result in all_results:
            if isinstance(result, dict) and result.get("type") == "stt":
                self.results["stt"][result["name"]] = result

        # In kết quả
        self._print_results()


async def main():
    tester = ASRPerformanceTester()
    await tester.run()


if __name__ == "__main__":
    asyncio.run(main())
