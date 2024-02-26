import math

from pyproj import CRS

from COGGenerateMinIO.COG_Translate_MinIO import cog_translate
import morecantile


def get_max_zoom_level(tms, resolution):
    # tms标准定义：https://github.com/developmentseed/morecantile?tab=readme-ov-file#defaults-grids
    if tms == "WGS1984Quad":
        max_zoom_level = morecantile.tms.get("WGS1984Quad").zoom_for_res(
            resolution * 180 / math.pi / 6378137)  # 分辨率由米转换为弧度
        print("max_zoom_level: ", max_zoom_level)
        return max_zoom_level
    elif tms == "WebMercatorQuad":
        max_zoom_level = morecantile.tms.get("WebMercatorQuad").zoom_for_res(resolution)
        print("max_zoom_level: ", max_zoom_level)
        return max_zoom_level
    elif tms == "rHEALPixCustom":
        north_square = 3
        south_square = 1
        lon_0 = 0
        crs = CRS.from_proj4(
            "+proj=rhealpix +ellps=WGS84 +south_square=" + str(south_square) + " +north_square=" + str(
                north_square) + " +lon_0=" + str(lon_0))
        extent = [-20015625.00, -15011718.75, 20015625.00, 15011718.75]
        tms = morecantile.TileMatrixSet.custom(extent=extent, crs=crs, matrix_scale=[4, 3])
        max_zoom_level = tms.zoom_for_res(resolution)
        print("max_zoom_level: ", max_zoom_level)
        return max_zoom_level
    else:
        return -1


def cog_generate(source_path, tms, resolution):
    cog_profile = {
        "driver": "GTiff",
        "interleave": "pixel",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "compress": "DEFLATE",
    }
    max_zoom_level = get_max_zoom_level(tms, resolution)
    print("max_zoom_level: ", max_zoom_level)
    if max_zoom_level == -1:
        print("tms参数错误")
    else:
        for zoom_level in range(0, max_zoom_level + 1):
            cog_translate(
                source_path,
                source_path.replace(".tif", "/") + str(tms) + "/" + source_path.split("/")[-1].replace(".tif", "") +
                "_" + tms + "_z" + str(zoom_level) + ".tif",
                cog_profile,
                web_optimized=True,
                tms=morecantile.tms.get("WGS1984Quad"),
                # https://github.com/developmentseed/morecantile?tab=readme-ov-file#defaults-grids
                overview_level=0,  # 概览级别
                zoom_level=zoom_level,  # 缩放级别
                # in_memory=True,  # 是否在内存中处理
                # aligned_levels=4, # 与几个层级对齐
                # additional_cog_metadata={
                #     "rhealpix:tile_format": "rHEALPix",
                # },
            )


if __name__ == "__main__":
    cog_generate("", "WebMercatorQuad", 30)
