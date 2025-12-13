import asyncio
import logging
import os
import statistics
import time
import concurrent.futures
from typing import Dict, Optional
import aiohttp
from tabulate import tabulate
from core.utils.llm import create_instance as create_llm_instance
from config.settings import load_config

# Đặt mức log toàn cục là WARNING để hạn chế log INFO
logging.basicConfig(level=logging.WARNING)

description = "Bài kiểm tra hiệu năng mô hình ngôn ngữ lớn"


class LLMPerformanceTester:
    def __init__(self):
        self.config = load_config()
        # Sử dụng bộ nội dung kiểm thử phù hợp với bối cảnh agent, kèm prompt hệ thống
        self.system_prompt = self._load_system_prompt()
        self.test_sentences = self.config.get("module_test", {}).get(
            "test_sentences",
            [
                "Chào bạn, hôm nay tôi hơi buồn, bạn có thể an ủi tôi không?",
                "Bạn giúp tôi xem thời tiết ngày mai như thế nào được không?",
                "Tôi muốn nghe một câu chuyện thú vị, bạn có thể kể cho tôi chứ?",
                "Bây giờ là mấy giờ? Hôm nay là thứ mấy?",
                "Tôi muốn đặt báo thức lúc 8 giờ sáng mai để nhắc tôi họp.",
            ],
        )
        self.results = {}

    def _load_system_prompt(self) -> str:
        """Nạp prompt hệ thống"""
        try:
            prompt_file = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "agent-base-prompt.txt"
            )
            with open(prompt_file, "r", encoding="utf-8") as f:
                content = f.read()
                # Thay thế biến trong template bằng giá trị phục vụ kiểm thử
                content = content.replace(
                    "{{base_prompt}}",
                    "Bạn là Tiểu Trí, một trợ lý AI thông minh và dễ mến",
                )
                content = content.replace(
                    "{{emojiList}}", "😀,😃,😄,😁,😊,😍,🤔,😮,😱,😢,😭,😴,😵,🤗,🙄"
                )
                content = content.replace("{{current_time}}", "17/08/2024 12:30:45")
                content = content.replace("{{today_date}}", "17/08/2024")
                content = content.replace("{{today_weekday}}", "Thứ Bảy")
                content = content.replace("{{local_address}}", "Bắc Kinh")
                content = content.replace("{{weather_info}}", "Hôm nay trời nắng, 25-32℃")
                return content
        except Exception as e:
            print(f"Không thể tải tệp prompt hệ thống: {e}")
            return "Bạn là Tiểu Trí, một trợ lý AI thông minh và dễ mến. Hãy trả lời người dùng bằng giọng điệu ấm áp, thân thiện."

    def _collect_response_sync(self, llm, messages, llm_name, sentence_start):
        """Hàm hỗ trợ thu thập phản hồi đồng bộ"""
        chunks = []
        first_token_received = False
        first_token_time = None

        try:
            response_generator = llm.response("perf_test", messages)
            chunk_count = 0
            for chunk in response_generator:
                chunk_count += 1
                # Sau mỗi số lượng chunk nhất định thì kiểm tra xem có cần dừng hay không
                if chunk_count % 10 == 0:
                    # Kiểm tra thread hiện tại có bị đánh dấu dừng hay chưa
                    import threading

                    if (
                        threading.current_thread().ident
                        != threading.main_thread().ident
                    ):
                        # Nếu không phải main thread, kiểm tra xem có nên dừng
                        pass

                # Kiểm tra chunk có chứa thông tin lỗi hay không
                chunk_str = str(chunk)
                if (
                    "exception" in chunk_str.lower()
                    or "error" in chunk_str.lower()
                    or "502" in chunk_str.lower()
                    or "bất thường" in chunk_str.lower()
                    or "lỗi" in chunk_str.lower()
                ):
                    error_msg = chunk_str.lower()
                    print(f"{llm_name} phản hồi chứa lỗi: {error_msg}")
                    # Ném ngoại lệ với thông tin lỗi
                    raise Exception(chunk_str)

                if not first_token_received and chunk.strip() != "":
                    first_token_time = time.time() - sentence_start
                    first_token_received = True
                    print(f"{llm_name} token đầu tiên: {first_token_time:.3f}s")
                chunks.append(chunk)
        except Exception as e:
            # Ghi lại thông tin lỗi chi tiết hơn
            error_msg = str(e).lower()
            print(f"{llm_name} gặp lỗi khi thu thập phản hồi: {error_msg}")
            # Với lỗi 502 hoặc lỗi mạng, ném ngoại lệ cho lớp trên xử lý
            if (
                "502" in error_msg
                or "bad gateway" in error_msg
                or "error code: 502" in error_msg
                or "bất thường" in str(e).lower()
                or "lỗi" in str(e).lower()
            ):
                raise e
            # Với lỗi khác có thể trả về kết quả từng phần
            return chunks, first_token_time

        return chunks, first_token_time

    async def _check_ollama_service(self, base_url: str, model_name: str) -> bool:
        """Kiểm tra trạng thái dịch vụ Ollama theo cách bất đồng bộ"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{base_url}/api/version") as response:
                    if response.status != 200:
                        print(f"Dịch vụ Ollama chưa khởi động hoặc không truy cập được: {base_url}")
                        return False
                async with session.get(f"{base_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        models = data.get("models", [])
                        if not any(model["name"] == model_name for model in models):
                            print(
                                f"Không tìm thấy mô hình Ollama {model_name}, hãy chạy `ollama pull {model_name}` trước"
                            )
                            return False
                    else:
                        print("Không thể lấy danh sách mô hình Ollama")
                        return False
                return True
            except Exception as e:
                print(f"Không thể kết nối tới dịch vụ Ollama: {str(e)}")
                return False

    async def _test_single_sentence(
        self, llm_name: str, llm, sentence: str
    ) -> Optional[Dict]:
        """Đo hiệu năng với một câu hỏi"""
        try:
            print(f"{llm_name} bắt đầu kiểm thử: {sentence[:20]}...")
            sentence_start = time.time()
            first_token_received = False
            first_token_time = None

            # Xây dựng thông điệp có prompt hệ thống
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": sentence},
            ]

            # Dùng asyncio.wait_for để kiểm soát timeout
            try:
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    # Tạo tác vụ thu thập phản hồi
                    future = executor.submit(
                        self._collect_response_sync,
                        llm,
                        messages,
                        llm_name,
                        sentence_start,
                    )

                    # Dùng asyncio.wait_for để áp timeout
                    try:
                        response_chunks, first_token_time = await asyncio.wait_for(
                            asyncio.wrap_future(future), timeout=10.0
                        )
                    except asyncio.TimeoutError:
                        print(f"{llm_name} kiểm thử quá thời gian (10 giây), bỏ qua")
                        # Hủy future bắt buộc
                        future.cancel()
                        # Chờ một chút để thread pool phản hồi việc hủy
                        try:
                            await asyncio.wait_for(
                                asyncio.wrap_future(future), timeout=1.0
                            )
                        except (
                            asyncio.TimeoutError,
                            concurrent.futures.CancelledError,
                            Exception,
                        ):
                            # Bỏ qua mọi ngoại lệ để chương trình tiếp tục chạy
                            pass
                        return None

            except Exception as timeout_error:
                print(f"{llm_name} gặp lỗi khi xử lý: {timeout_error}")
                return None

            response_time = time.time() - sentence_start
            print(f"{llm_name} hoàn thành phản hồi: {response_time:.3f}s")

            return {
                "name": llm_name,
                "type": "llm",
                "first_token_time": first_token_time,
                "response_time": response_time,
            }
        except Exception as e:
            error_msg = str(e).lower()
            # Kiểm tra xem có phải lỗi 502 hoặc lỗi mạng hay không
            if (
                "502" in error_msg
                or "bad gateway" in error_msg
                or "error code: 502" in error_msg
            ):
                print(f"{llm_name} gặp lỗi 502, bỏ qua kiểm thử")
                return {
                    "name": llm_name,
                    "type": "llm",
                    "errors": 1,
                    "error_type": "Lỗi mạng 502",
                }
            print(f"{llm_name} kiểm thử câu thất bại: {str(e)}")
            return None

    async def _test_llm(self, llm_name: str, config: Dict) -> Dict:
        """Kiểm tra bất đồng bộ hiệu năng từng LLM"""
        try:
            # Với Ollama, bỏ qua kiểm tra api_key và xử lý đặc biệt
            if llm_name == "Ollama":
                base_url = config.get("base_url", "http://localhost:11434")
                model_name = config.get("model_name")
                if not model_name:
                    print("Ollama chưa cấu hình model_name")
                    return {
                        "name": llm_name,
                        "type": "llm",
                        "errors": 1,
                        "error_type": "Lỗi mạng",
                    }

                if not await self._check_ollama_service(base_url, model_name):
                    return {
                        "name": llm_name,
                        "type": "llm",
                        "errors": 1,
                        "error_type": "Lỗi mạng",
                    }
            else:
                if "api_key" in config and any(
                    x in config["api_key"] for x in ["你的", "placeholder", "sk-xxx"]
                ):
                    print(f"Bỏ qua LLM chưa cấu hình: {llm_name}")
                    return {
                        "name": llm_name,
                        "type": "llm",
                        "errors": 1,
                        "error_type": "Lỗi cấu hình",
                    }

            # Lấy kiểu thực tế (tương thích cấu hình cũ)
            module_type = config.get("type", llm_name)
            llm = create_llm_instance(module_type, config)

            # Đồng bộ sử dụng UTF-8
            test_sentences = [
                s.encode("utf-8").decode("utf-8") for s in self.test_sentences
            ]

            # Tạo tác vụ kiểm thử cho từng câu
            sentence_tasks = []
            for sentence in test_sentences:
                sentence_tasks.append(
                    self._test_single_sentence(llm_name, llm, sentence)
                )

            # Thực thi song song các kiểm thử câu và xử lý ngoại lệ
            sentence_results = await asyncio.gather(
                *sentence_tasks, return_exceptions=True
            )

            # Xử lý kết quả, loại bỏ ngoại lệ và giá trị None
            valid_results = []
            for result in sentence_results:
                if isinstance(result, dict) and result is not None:
                    valid_results.append(result)
                elif isinstance(result, Exception):
                    error_msg = str(result).lower()
                    if "502" in error_msg or "bad gateway" in error_msg:
                        print(f"{llm_name} gặp lỗi 502, bỏ qua câu kiểm thử này")
                        return {
                            "name": llm_name,
                            "type": "llm",
                            "errors": 1,
                            "error_type": "Lỗi mạng 502",
                        }
                    else:
                        print(f"{llm_name} câu kiểm thử gặp ngoại lệ: {result}")

            if not valid_results:
                print(f"{llm_name} không có dữ liệu hợp lệ, có thể do lỗi mạng hoặc cấu hình")
                return {
                    "name": llm_name,
                    "type": "llm",
                    "errors": 1,
                    "error_type": "Lỗi mạng",
                }

            # Kiểm tra số lượng kết quả hợp lệ, quá ít thì xem là thất bại
            if len(valid_results) < len(test_sentences) * 0.3:  # Cần ít nhất 30% thành công
                print(
                    f"{llm_name} có quá ít câu kiểm thử thành công ({len(valid_results)}/{len(test_sentences)}), có thể mạng không ổn định hoặc API gặp vấn đề"
                )
                return {
                    "name": llm_name,
                    "type": "llm",
                    "errors": 1,
                    "error_type": "Lỗi mạng",
                }

            first_token_times = [
                r["first_token_time"]
                for r in valid_results
                if r.get("first_token_time")
            ]
            response_times = [r["response_time"] for r in valid_results]

            # Lọc bỏ dữ liệu bất thường (lớn hơn 3 độ lệch chuẩn)
            if len(response_times) > 1:
                mean = statistics.mean(response_times)
                stdev = statistics.stdev(response_times)
                filtered_times = [t for t in response_times if t <= mean + 3 * stdev]
            else:
                filtered_times = response_times

            return {
                "name": llm_name,
                "type": "llm",
                "avg_response": sum(response_times) / len(response_times),
                "avg_first_token": (
                    sum(first_token_times) / len(first_token_times)
                    if first_token_times
                    else 0
                ),
                "success_rate": f"{len(valid_results)}/{len(test_sentences)}",
                "errors": 0,
            }
        except Exception as e:
            error_msg = str(e).lower()
            if "502" in error_msg or "bad gateway" in error_msg:
                print(f"LLM {llm_name} gặp lỗi 502, bỏ qua kiểm thử")
            else:
                print(f"LLM {llm_name} kiểm thử thất bại: {str(e)}")
            error_type = "Lỗi mạng"
            if "timeout" in str(e).lower():
                error_type = "Kết nối quá thời gian"
            return {
                "name": llm_name,
                "type": "llm",
                "errors": 1,
                "error_type": error_type,
            }

    def _print_results(self):
        """In kết quả kiểm thử"""
        print("\n" + "=" * 50)
        print("Kết quả kiểm tra hiệu năng LLM")
        print("=" * 50)

        if not self.results:
            print("Không có kết quả kiểm thử khả dụng")
            return

        headers = ["Tên mô hình", "Thời gian phản hồi TB(s)", "Thời gian token đầu(s)", "Tỉ lệ thành công", "Trạng thái"]
        table_data = []

        # Thu thập và phân loại dữ liệu
        valid_results = []
        error_results = []

        for name, data in self.results.items():
            if data["errors"] == 0:
                # Kết quả hợp lệ
                avg_response = f"{data['avg_response']:.3f}"
                avg_first_token = (
                    f"{data['avg_first_token']:.3f}"
                    if data["avg_first_token"] > 0
                    else "-"
                )
                success_rate = data.get("success_rate", "N/A")
                status = "✅ Bình thường"

                # Lưu giá trị phục vụ việc sắp xếp
                first_token_value = (
                    data["avg_first_token"]
                    if data["avg_first_token"] > 0
                    else float("inf")
                )

                valid_results.append(
                    {
                        "name": name,
                        "avg_response": avg_response,
                        "avg_first_token": avg_first_token,
                        "success_rate": success_rate,
                        "status": status,
                        "sort_key": first_token_value,
                    }
                )
            else:
                # Kết quả lỗi
                avg_response = "-"
                avg_first_token = "-"
                success_rate = "0/5"

                # Lấy loại lỗi cụ thể
                error_type = data.get("error_type", "Lỗi mạng")
                status = f"❌ {error_type}"

                error_results.append(
                    [name, avg_response, avg_first_token, success_rate, status]
                )

        # Sắp xếp theo thời gian token đầu tăng dần
        valid_results.sort(key=lambda x: x["sort_key"])

        # Chuyển kết quả hợp lệ đã sắp xếp sang dữ liệu bảng
        for result in valid_results:
            table_data.append(
                [
                    result["name"],
                    result["avg_response"],
                    result["avg_first_token"],
                    result["success_rate"],
                    result["status"],
                ]
            )

        # Đưa các bản ghi lỗi vào cuối bảng
        table_data.extend(error_results)

        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        print("\nGhi chú kiểm thử:")
        print("- Nội dung kiểm thử: kịch bản hội thoại agent với prompt hệ thống đầy đủ")
        print("- Kiểm soát timeout: tối đa 10 giây cho mỗi yêu cầu")
        print("- Xử lý lỗi: tự động bỏ qua mô hình gặp lỗi 502 hoặc sự cố mạng")
        print("- Tỉ lệ thành công: số câu phản hồi thành công / tổng số câu kiểm thử")
        print("\nKiểm thử hoàn tất!")

    async def run(self):
        """Chạy toàn bộ bài kiểm tra bất đồng bộ"""
        print("Bắt đầu lọc các module LLM khả dụng...")

        # Tạo toàn bộ tác vụ kiểm thử
        all_tasks = []

        # Tác vụ kiểm thử LLM
        if self.config.get("LLM") is not None:
            for llm_name, config in self.config.get("LLM", {}).items():
                # Kiểm tra tính hợp lệ của cấu hình
                if llm_name == "CozeLLM":
                    if any(x in config.get("bot_id", "") for x in ["你的"]) or any(
                        x in config.get("user_id", "") for x in ["你的"]
                    ):
                        print(f"LLM {llm_name} chưa cấu hình bot_id/user_id, bỏ qua")
                        continue
                elif "api_key" in config and any(
                    x in config["api_key"] for x in ["你的", "placeholder", "sk-xxx"]
                ):
                    print(f"LLM {llm_name} chưa cấu hình api_key, bỏ qua")
                    continue

                # Với Ollama, kiểm tra trạng thái dịch vụ trước
                if llm_name == "Ollama":
                    base_url = config.get("base_url", "http://localhost:11434")
                    model_name = config.get("model_name")
                    if not model_name:
                        print("Ollama chưa cấu hình model_name")
                        continue

                    if not await self._check_ollama_service(base_url, model_name):
                        continue

                print(f"Thêm tác vụ kiểm tra LLM: {llm_name}")
                all_tasks.append(self._test_llm(llm_name, config))

        print(f"\nTìm thấy {len(all_tasks)} module LLM khả dụng")
        print("\nBắt đầu kiểm tra song song tất cả module...\n")

        # Thực thi song song mọi tác vụ và đặt timeout riêng cho từng tác vụ
        async def test_with_timeout(task, timeout=30):
            """Thêm cơ chế timeout bảo vệ cho từng tác vụ kiểm thử"""
            try:
                return await asyncio.wait_for(task, timeout=timeout)
            except asyncio.TimeoutError:
                print(f"Tác vụ kiểm thử quá thời gian ({timeout} giây), bỏ qua")
                return {
                    "name": "Unknown",
                    "type": "llm",
                    "errors": 1,
                    "error_type": "Kết nối quá thời gian",
                }
            except Exception as e:
                print(f"Tác vụ kiểm thử gặp ngoại lệ: {str(e)}")
                return {
                    "name": "Unknown",
                    "type": "llm",
                    "errors": 1,
                    "error_type": "Lỗi mạng",
                }

        # Bao bọc timeout bảo vệ cho từng tác vụ
        protected_tasks = [test_with_timeout(task) for task in all_tasks]

        # Thực thi song song mọi tác vụ kiểm thử
        all_results = await asyncio.gather(*protected_tasks, return_exceptions=True)

        # Xử lý kết quả
        for result in all_results:
            if isinstance(result, dict):
                if result.get("errors") == 0:
                    self.results[result["name"]] = result
                else:
                    # Vẫn ghi lại lỗi để hiển thị trạng thái thất bại
                    if result.get("name") != "Unknown":
                        self.results[result["name"]] = result
            elif isinstance(result, Exception):
                print(f"Lỗi khi xử lý kết quả kiểm thử: {str(result)}")

        # In kết quả
        print("\nTạo báo cáo kiểm thử...")
        self._print_results()


async def main():
    tester = LLMPerformanceTester()
    await tester.run()


if __name__ == "__main__":
    asyncio.run(main())
