import os

import minio
from Bytes_Parse import *
from Tile_Deserializer import *

MINIO_CONF = {
    'endpoint': '125.220.153.25:9006',
    'access_key': 'lrx',
    'secret_key': 'lrx_lucky316',
    'secure': False
}

type_array = [
    0,  # "???"
    1,  # byte //8-bit unsigned integer
    1,  # ascii//8-bit byte that contains a 7-bit ASCII code; the last byte must be NUL (binary zero)
    2,  # short",2),//16-bit (2-byte) unsigned integer.
    4,  # long",4),//32-bit (4-byte) unsigned integer.
    8,  # rational",8),//Two LONGs: the first represents the numerator of a fraction; the second, the denominator.
    1,  # sbyte",1),//An 8-bit signed (twos-complement) integer
    1,  # undefined",1),//An 8-bit byte that may contain anything, depending on the definition of the field
    2,  # sshort",1),//A 16-bit (2-byte) signed (twos-complement) integer.
    4,  # slong",1),// A 32-bit (4-byte) signed (twos-complement) integer.
    8,  # srational",1),//Two SLONG’s: the first represents the numerator of a fraction, the second the denominator.
    4,  # float",4),//Single precision (4-byte) IEEE format
    8  # double",8)//Double precision (8-byte) IEEE format
]


def minio_get_object(bucket, object, offset, length):
    client = minio.Minio(**MINIO_CONF)
    if not client.bucket_exists(bucket):
        return None
    data = client.get_object(bucket, object, offset, length)
    return data.data


def cog_header_bytes_parse(header_bytes):
    # Decode IFH
    image_width = []
    image_height = []
    bit_per_sample = []
    tile_offsets = []
    tile_byte_counts = []
    cell_scale = []
    geo_transform = []
    crs = ''
    band_count = []
    sample_format = []
    gdal_metadata = ''
    gdal_nodata = ''

    ifh = get_int_ii(header_bytes, 4, 4)
    overview_level = -1
    # Decode IFD
    while ifh != 0:
        de_count = get_int_ii(header_bytes, ifh, 2)
        ifh += 2
        for _ in range(de_count):
            tag_index = get_int_ii(header_bytes, ifh, 2)
            type_index = get_int_ii(header_bytes, ifh + 2, 2)
            count = get_int_ii(header_bytes, ifh + 4, 4)
            # Find the position of the data first
            p_data = ifh + 8
            total_size = type_array[type_index] * count
            if total_size > 4:
                p_data = get_int_ii(header_bytes, p_data, 4)
            # Read and store the values based on the Tag using GetDEValue
            type_size = type_array[type_index]
            if tag_index == 256:  # ImageWidth
                image_width.append(get_int_ii(header_bytes, p_data, type_size))
                overview_level += 1
            elif tag_index == 257:  # ImageLength/ImageHeight
                image_height.append(get_int_ii(header_bytes, p_data, type_size))
            elif tag_index == 258:
                bit_per_sample.append(get_int_ii(header_bytes, p_data, type_size))
            elif tag_index == 277:  # SamplesPerPixel
                band_count.append(get_int_ii(header_bytes, p_data, type_size))
            elif tag_index == 324:  # tileOffsets
                tile_offsets.append(
                    get_bytes_array(p_data, type_size, header_bytes, image_width[overview_level],
                                    image_height[overview_level], band_count[overview_level]))
            elif tag_index == 325:  # tileByteCounts
                tile_byte_counts.append(
                    get_bytes_array(p_data, type_size, header_bytes, image_width[overview_level],
                                    image_height[overview_level], band_count[overview_level]))
            elif tag_index == 339:  # SampleFormat
                sample_format.append(get_int_ii(header_bytes, p_data, type_size))
            elif tag_index == 33550:  # cellWidth
                cell_scale = get_double_cell(p_data, type_size, count, header_bytes)
            elif tag_index == 33922:  # geoTransform
                geo_transform = get_double_trans(p_data, type_size, count, header_bytes)
            elif tag_index == 34737:  # Spatial reference
                crs = get_string(header_bytes, p_data, type_size * count - 1)
            elif tag_index == 42112:  # GDAL_METADATA
                gdal_metadata = get_string(header_bytes, p_data, type_size * count - 1)
            elif tag_index == 42113:  # GDAL_NODATA
                gdal_nodata = get_string(header_bytes, p_data, type_size * count - 1)
            # Previous
            ifh += 12
        ifh = get_int_ii(header_bytes, ifh, 4)
    result_dict = {
        'image_width': image_width,
        'image_height': image_height,
        'bit_per_sample': bit_per_sample,
        'band_count': band_count,
        'tile_offsets': tile_offsets,
        'tile_byte_counts': tile_byte_counts,
        'sample_format': sample_format,
        # 1: unsigned integer data, 2: two’s complement signed integer data, 3: IEEE floating point data, 4: undefined data format
        'cell_scale': cell_scale,
        'geo_transform': geo_transform,
        'crs': crs,
        'gdal_metadata': gdal_metadata,
        'gdal_nodata': gdal_nodata
    }
    return result_dict


def get_tile(bucket_name, object_path, tile_offset, tile_byte_count):
    return minio_get_object(bucket_name, object_path, tile_offset, tile_byte_count)


if __name__ == '__main__':
    bucket_name = 'geo-stream-cube'
    object_name = 'landsat_a_4326'
    object_path = 'test/' + object_name + '.tif'
    overview_level = 0
    header_bytes_bytes = minio_get_object(bucket_name, object_path, 0, 1500000)
    result_dict = cog_header_bytes_parse(header_bytes_bytes)

    path_to_check = 'D:\\组内项目\\DGGS\\data\\cogtest_2_different_landsat\\' + object_name + '\\'
    # 判断路径是否存在
    if not os.path.exists(path_to_check):
        # 如果路径不存在，则创建路径
        os.makedirs(path_to_check)
        print(f"路径 {path_to_check} 创建成功")
    else:
        print(f"路径 {path_to_check} 已经存在")
    for overview_level in range(result_dict['tile_offsets'].__len__() - 3, result_dict['tile_offsets'].__len__()):
        for row_key in range(0, result_dict['tile_offsets'][overview_level].__len__()):
            for col_key in range(0, result_dict['tile_offsets'][overview_level][0].__len__()):
                tile_bytes = get_tile(bucket_name, object_path,
                                      result_dict['tile_offsets'][overview_level][row_key][col_key],
                                      result_dict['tile_byte_counts'][overview_level][row_key][col_key])
                bytes_to_geotiff(tile_bytes, result_dict,
                                 path_to_check + object_name + '_' + str(overview_level) + '_' + str(
                                     row_key) + '_' + str(col_key) + '.tif', overview_level, row_key, col_key)
