import struct

def decode_opus_from_file(input_file):
    """
    Giải mã dữ liệu Opus từ tệp p3 và trả về danh sách gói Opus cùng tổng thời lượng.
    """
    opus_datas = []
    total_frames = 0
    sample_rate = 16000  # Tần số lấy mẫu của tệp
    frame_duration_ms = 60  # Độ dài khung
    frame_size = int(sample_rate * frame_duration_ms / 1000)

    with open(input_file, 'rb') as f:
        while True:
            # Đọc header (4 byte): [1 byte loại, 1 byte dự phòng, 2 byte độ dài]
            header = f.read(4)
            if not header:
                break

            # Giải unpack thông tin header
            _, _, data_len = struct.unpack('>BBH', header)

            # Đọc dữ liệu Opus theo độ dài chỉ định trong header
            opus_data = f.read(data_len)
            if len(opus_data) != data_len:
                raise ValueError(f"Data length({len(opus_data)}) mismatch({data_len}) in the file.")

            opus_datas.append(opus_data)
            total_frames += 1

    # Tính tổng thời lượng
    total_duration = (total_frames * frame_duration_ms) / 1000.0
    return opus_datas, total_duration

def decode_opus_from_bytes(input_bytes):
    """
    Giải mã dữ liệu Opus từ dữ liệu nhị phân p3 và trả về danh sách gói cùng tổng thời lượng.
    """
    import io
    opus_datas = []
    total_frames = 0
    sample_rate = 16000  # Tần số lấy mẫu của tệp
    frame_duration_ms = 60  # Độ dài khung
    frame_size = int(sample_rate * frame_duration_ms / 1000)

    f = io.BytesIO(input_bytes)
    while True:
        header = f.read(4)
        if not header:
            break
        _, _, data_len = struct.unpack('>BBH', header)
        opus_data = f.read(data_len)
        if len(opus_data) != data_len:
            raise ValueError(f"Data length({len(opus_data)}) mismatch({data_len}) in the bytes.")
        opus_datas.append(opus_data)
        total_frames += 1

    total_duration = (total_frames * frame_duration_ms) / 1000.0
    return opus_datas, total_duration
