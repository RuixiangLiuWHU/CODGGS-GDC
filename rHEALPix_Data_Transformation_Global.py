import fiona
import os
import rasterio
import rasterio.features
import rasterio.warp
import rhealpixdggs.dggs as rhp
from rasterio.transform import Affine
from rhealpixdggs.ellipsoids import Ellipsoid, WGS84_A, WGS84_F

north_square = 1
south_square = 0
lon_0 = 0
N_side = 2

rdggs = rhp.RHEALPixDGGS(ellipsoid=Ellipsoid(a=WGS84_A, f=WGS84_F, lon_0=10), north_square=north_square,
                         south_square=south_square, N_side=N_side)
rhealpix_common_proj_string = f"+proj=rhealpix +south_square={south_square} +north_square={north_square} " \
                              f"+lon_0={lon_0}"
resolution_idx = 7


def cartesian_dist(x1, y1, x2, y2):
    return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5


def align_transform(rdggs, transform, dst_resolution_idx):
    current_left = transform[2]
    current_top = transform[5]
    current_topleft_cell = rdggs.cell_from_point(dst_resolution_idx, (current_left, current_top))
    _, new_left, new_top = min(
        [(cartesian_dist(current_left, current_top, x, y), x, y) for x, y in current_topleft_cell.vertices()])

    return Affine.translation(new_left - current_left, new_top - current_top) * transform


def raster2rhealpix(rdggs, rhealpix_common_proj_string, input_file_path, output_file_path, dst_resolution_idx,
                    resampling):
    # dst_resolution = rdggs.cell_width(dst_resolution_idx)

    with rasterio.open(input_file_path) as raster:
        left = -180
        top = 90
        right = 180
        bottom = -90
        input_crs = raster.profile["crs"]
        dst_crs = rhealpix_common_proj_string

        transform, width, height = rasterio.warp.calculate_default_transform(
            input_crs, dst_crs, raster.width, raster.height,
            left=left, right=right, top=top, bottom=bottom,
            dst_width=N_side ** resolution_idx * 4, dst_height=N_side ** resolution_idx * 3)

        # This should do the alignment, but it seems it does not. Horizontal alignment seems fine, but
        # vertical alignment looks like it is off by half a pixel, giving cell centroids aligned with
        # the center of the pixels in the horizontal axis, but with their edges in the vertical one
        # (so neither in the center of the pixels nor in a corner, which is problematic)
        # transform, width, height = rasterio.warp.aligned_target(transform, width, height, dst_resolution)
        # We have to do a similar operation manually
        # transform = align_transform(rdggs, transform, dst_resolution_idx)

        set_src_nodata = raster.nodata
        set_dst_nodata = raster.nodata

        kwargs = raster.meta.copy()
        kwargs.update({
            'driver': 'GTiff',
            'compress': 'DEFLATE',
            'crs': dst_crs,
            'transform': transform,
            'width': width,
            'height': height,
            'nodata': set_dst_nodata
        })
        with rasterio.open(output_file_path, 'w', **kwargs) as dst:
            for i in range(1, raster.count + 1):
                rasterio.warp.reproject(
                    source=rasterio.band(raster, i),
                    destination=rasterio.band(dst, i),
                    src_transform=raster.transform,
                    dst_transform=transform,
                    src_nodata=set_src_nodata,
                    dst_nodata=set_dst_nodata,
                    dst_crs=dst_crs,
                    resampling=resampling)


def vector_file_to_rhealpix(rdggs, input_file_path, output_file_path, dst_resolution_idx, input_crs):
    dst_resolution = rdggs.cell_width(dst_resolution_idx)

    with fiona.open(input_file_path, "r") as vectorfile:
        input_features = [feature for feature in vectorfile]
        left, top, right, bottom = (
            vectorfile.bounds[0], vectorfile.bounds[3], vectorfile.bounds[2], vectorfile.bounds[1])

    width = round(abs(right - left) / dst_resolution)
    height = round(abs(top - bottom) / dst_resolution)

    transform, width, height = rasterio.warp.calculate_default_transform(
        input_crs, input_crs, width, height, left=left, right=right, top=top, bottom=bottom)

    data_to_include = [(feature["geometry"], 2) for feature in input_features]

    image = rasterio.features.rasterize(
        data_to_include,
        transform=transform,
        all_touched=False,
        out_shape=(height, width))

    tmp_file_path = output_file_path + "_tmp"

    with rasterio.open(
            tmp_file_path, 'w',
            driver='GTiff',
            compress='DEFLATE',
            dtype=rasterio.uint16,
            crs=input_crs,
            transform=transform,
            count=1,
            width=width,
            height=height) as dst:
        dst.write(image, indexes=1)

    raster2rhealpix(rdggs, rhealpix_common_proj_string, tmp_file_path, output_file_path, resolution_idx,
                    rasterio.enums.Resampling.nearest)
    os.remove(tmp_file_path)


input_file_path = r"D:\组内项目\DGGS\data\test\relative_humidity_20200101T000000Z.tif"
output_file_path = r"D:\组内项目\DGGS\data\test\relative_humidity_20200101T000000Z-rHEALPix-" + str(N_side) + "_" + str(
    resolution_idx) + ".tif"

raster2rhealpix(rdggs, rhealpix_common_proj_string, input_file_path, output_file_path,
                resolution_idx, rasterio.enums.Resampling.nearest)

# input_file_path = "/home/C_GLS_SCE500/c_gls_SCE500_202204260000_CEURO_MODIS_V1.0.1.nc"
# output_file_path = "/home/c_gls_SCE500_202204260000_CEURO_MODIS_V1.0.1-RHEALPIX.tif"
#
# raster2rhealpix(rdggs, rhealpix_common_proj_string, input_file_path, output_file_path,
#                 resolution_idx, rasterio.enums.Resampling.nearest)
#
# input_file_path = "/home/Aragón/Aragón_ETRS89_30N.shp"
# output_file_path = "/home/Aragón-RHEALPIX_res9.tif"
# vector_file_to_rhealpix(rdggs, input_file_path, output_file_path, resolution_idx,
#                         input_crs=rasterio.crs.CRS.from_epsg(25830))
