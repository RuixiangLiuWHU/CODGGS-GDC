import struct


def get_int_ii(pd, start_pos, length):
    value = 0
    for i in range(length):
        value |= pd[start_pos + i] << i * 8
        if value < 0:
            value += 256 << i * 8
    return value


def get_bytes_array(start_pos, type_size, header, image_width, image_height, band_count):
    strip_offsets = []
    if image_width % 256 == 0:
        tile_count_x = image_width // 256
    else:
        tile_count_x = image_width // 256 + 1
    if image_height % 256 == 0:
        tile_count_y = image_height // 256
    else:
        tile_count_y = image_height // 256 + 1
    for _ in range(band_count):
        for i in range(tile_count_y):
            offsets = []
            for j in range(tile_count_x):
                v = get_long(header, start_pos + (i * tile_count_x + j) * type_size, type_size)
                offsets.append(v)
            strip_offsets.append(offsets)
    return strip_offsets


def get_long(header_bytes_bytes, start, length):
    value = 0
    for i in range(length):
        value |= (header_bytes_bytes[start + i] & 0xff) << (8 * i)
        if value < 0:
            value += 256 << (i * 8)
    return value


def get_double_cell(start_pos, type_size, count, header):
    cell = []
    for i in range(count):
        v = get_double(header, start_pos + i * type_size, type_size)
        cell.append(v)
    return cell


def get_double(pd, start_pos, length):
    value = 0
    for i in range(length):
        value |= (pd[start_pos + i] & 0xff) << (8 * i)
        if value < 0:
            value += 256 << i * 8
    return struct.unpack('d', struct.pack('Q', value))[0]


def get_double_trans(start_pos, type_size, count, header):
    geo_trans = []
    for i in range(count):
        v = get_double(header, start_pos + i * type_size, type_size)
        geo_trans.append(v)
    return geo_trans


def get_string(pd, start_pos, length):
    str_get = bytearray(length)
    str_get[:] = pd[start_pos:start_pos + length]
    return str_get.decode("ascii")
