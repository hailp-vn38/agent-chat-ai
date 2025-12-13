import os
import re
import sys
import importlib
from app.core.logger import setup_logging

# Thêm thư mục gốc dự án vào đường dẫn Python
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
sys.path.insert(0, project_root)

logger = setup_logging()

punctuation_set = {
    "，",
    ",",  # Dấu phẩy Trung + Anh
    "。",
    ".",  # Dấu chấm Trung + Anh
    "！",
    "!",  # Dấu chấm than Trung + Anh
    """,
    """,
    '"',  # Dấu ngoặc kép Trung + Anh
    "：",
    ":",  # Dấu hai chấm Trung + Anh
    "-",
    "－",  # Gạch nối tiếng Anh + gạch ngang full-width
    "、",  # Dấu ngắt câu tiếng Trung
    "[",
    "]",  # Ngoặc vuông
    "【",
    "】",  # Ngoặc vuông tiếng Trung
    "~",  # Dấu ngã
}


def create_instance(class_name, *args, **kwargs):
    # Tạo instance TTS
    # Đường dẫn trong src/app/ai/providers/tts
    tts_path = os.path.join(
        project_root, "app", "ai", "providers", "tts", f"{class_name}.py"
    )

    if os.path.exists(tts_path):
        lib_name = f"app.ai.providers.tts.{class_name}"
        if lib_name not in sys.modules:
            sys.modules[lib_name] = importlib.import_module(lib_name)
        return sys.modules[lib_name].TTSProvider(*args, **kwargs)

    raise ValueError(
        f"Loại TTS không được hỗ trợ: {class_name}, vui lòng kiểm tra cấu hình type. Đường dẫn: {tts_path}"
    )


class MarkdownCleaner:
    """
    Đóng gói logic làm sạch Markdown: chỉ cần gọi MarkdownCleaner.clean_markdown(text)
    """

    # Ký tự công thức
    NORMAL_FORMULA_CHARS = re.compile(r"[a-zA-Z\\^_{}\+\-\(\)\[\]=]")

    @staticmethod
    def _replace_inline_dollar(m: re.Match) -> str:
        """
        Chỉ cần bắt được "$...$" đầy đủ:
          - Nếu bên trong có ký tự công thức điển hình => bỏ ký tự $ hai bên
          - Nếu không (chỉ số/đơn vị tiền tệ, ...) => giữ nguyên "$...$"
        """
        content = m.group(1)
        if MarkdownCleaner.NORMAL_FORMULA_CHARS.search(content):
            return content
        else:
            return m.group(0)

    @staticmethod
    def _replace_table_block(match: re.Match) -> str:
        """
        Gọi hàm này khi khớp được một khối bảng hoàn chỉnh.
        """
        block_text = match.group("table_block")
        lines = block_text.strip("\n").split("\n")

        parsed_table = []
        for line in lines:
            line_stripped = line.strip()
            if re.match(r"^\|\s*[-:]+\s*(\|\s*[-:]+\s*)+\|?$", line_stripped):
                continue
            columns = [
                col.strip() for col in line_stripped.split("|") if col.strip() != ""
            ]
            if columns:
                parsed_table.append(columns)

        if not parsed_table:
            return ""

        headers = parsed_table[0]
        data_rows = parsed_table[1:] if len(parsed_table) > 1 else []

        lines_for_tts = []
        if len(parsed_table) == 1:
            # Chỉ có một dòng
            only_line_str = ", ".join(parsed_table[0])
            lines_for_tts.append(f"Bảng một dòng: {only_line_str}")
        else:
            lines_for_tts.append(f"Tiêu đề bảng: {', '.join(headers)}")
            for i, row in enumerate(data_rows, start=1):
                row_str_list = []
                for col_index, cell_val in enumerate(row):
                    if col_index < len(headers):
                        row_str_list.append(f"{headers[col_index]} = {cell_val}")
                    else:
                        row_str_list.append(cell_val)
                lines_for_tts.append(f"Dòng {i}: {', '.join(row_str_list)}")

        return "\n".join(lines_for_tts) + "\n"

    # Tiền biên dịch toàn bộ biểu thức chính quy (theo tần suất sử dụng)
    # Các phương thức replace_xxx phải được định nghĩa trước để có thể tham chiếu trong danh sách.
    REGEXES = [
        (re.compile(r"```.*?```", re.DOTALL), ""),  # Khối mã
        (re.compile(r"^#+\s*", re.MULTILINE), ""),  # Tiêu đề
        (re.compile(r"(\*\*|__)(.*?)\1"), r"\2"),  # Chữ đậm
        (re.compile(r"(\*|_)(?=\S)(.*?)(?<=\S)\1"), r"\2"),  # Chữ nghiêng
        (re.compile(r"!\[.*?\]\(.*?\)"), ""),  # Hình ảnh
        (re.compile(r"\[(.*?)\]\(.*?\)"), r"\1"),  # Liên kết
        (re.compile(r"^\s*>+\s*", re.MULTILINE), ""),  # Trích dẫn
        (
            re.compile(r"(?P<table_block>(?:^[^\n]*\|[^\n]*\n)+)", re.MULTILINE),
            _replace_table_block,
        ),
        (re.compile(r"^\s*[*+-]\s*", re.MULTILINE), "- "),  # Danh sách
        (re.compile(r"\$\$.*?\$\$", re.DOTALL), ""),  # Công thức dạng khối
        (
            re.compile(r"(?<![A-Za-z0-9])\$([^\n$]+)\$(?![A-Za-z0-9])"),
            _replace_inline_dollar,
        ),
        (re.compile(r"\n{2,}"), "\n"),  # Dòng trống dư
    ]

    @staticmethod
    def clean_markdown(text: str) -> str:
        """
        Hàm vào chính: lần lượt áp dụng toàn bộ regex để loại bỏ hoặc thay thế phần tử Markdown
        """
        # Kiểm tra văn bản có chỉ gồm tiếng Anh và dấu câu cơ bản hay không
        if text and all(
            (c.isascii() or c.isspace() or c in punctuation_set) for c in text
        ):
            # Giữ nguyên khoảng trắng gốc và trả về ngay
            return text

        for regex, replacement in MarkdownCleaner.REGEXES:
            text = regex.sub(replacement, text)
        return text.strip()
