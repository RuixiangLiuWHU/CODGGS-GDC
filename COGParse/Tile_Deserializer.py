import rasterio
from rasterio.transform import from_bounds
import numpy as np
from rasterio.crs import CRS


def bytes_to_geotiff(byte_array, result_dict, output_file, overview_level, row_key, col_key):
    data_type = get_data_type(result_dict['sample_format'][overview_level],
                              result_dict['bit_per_sample'][overview_level])
    # Convert bytes to numpy array
    data_array = np.frombuffer(byte_array, dtype=data_type)
    data_array = data_array.reshape(256, 256)
    data_array = data_array[::-1, :]

    # Define metadata
    metadata = {
        'width': 256,
        'height': 256,
        'count': 1,
        'dtype': data_type,
        'driver': 'GTiff',
        'crs': CRS.from_user_input('EPSG:4326'),
        'transform': from_bounds(
            result_dict['geo_transform'][3] + result_dict['cell_scale'][0] * 2 ** overview_level * 256 * col_key,
            result_dict['geo_transform'][4] - result_dict['cell_scale'][1] * 2 ** overview_level * 256 * row_key,
            result_dict['geo_transform'][3] + result_dict['cell_scale'][0] * 2 ** overview_level * 256 * (col_key + 1),
            result_dict['geo_transform'][4] - result_dict['cell_scale'][1] * 2 ** overview_level * 256 * (row_key + 1),
            256, 256)
        # 'transform': from_origin(result_dict['geo_transform'][0], result_dict['geo_transform'][1],
        #                          result_dict['cell_scale'][0] * (2 ** overview_level),
        #                          result_dict['cell_scale'][1] * (2 ** overview_level))
        # Adjust the origin and resolution
    }

    # Write the GeoTIFF
    with rasterio.open(output_file, 'w', **metadata) as dst:
        dst.write(data_array, 1)


def get_data_type(sample_format, bit_per_sample):
    if sample_format == 1:
        if bit_per_sample == 8:
            return np.uint8
        elif bit_per_sample == 16:
            return np.uint16
        elif bit_per_sample == 32:
            return np.uint32
        elif bit_per_sample == 64:
            return np.uint64
    elif sample_format == 2:
        if bit_per_sample == 8:
            return np.int8
        elif bit_per_sample == 16:
            return np.int16
        elif bit_per_sample == 32:
            return np.int32
        elif bit_per_sample == 64:
            return np.int64
    elif sample_format == 3:
        if bit_per_sample == 32:
            return np.float32
        elif bit_per_sample == 64:
            return np.float64
    else:
        return None
