import math

from pyproj import CRS

from COGGenerate.COG_Translate import cog_translate
import morecantile

cog_profile = {
    "driver": "GTiff",
    "interleave": "pixel",
    "tiled": True,
    "blockxsize": 256,
    "blockysize": 256,
    "compress": "DEFLATE",
}

resolution = 30
max_zoom_level = morecantile.tms.get("WGS1984Quad").zoom_for_res(30 * 180 / math.pi / 6378137) # 分辨率由米转换为弧度
print("max_zoom_level: ", max_zoom_level)
for zoom_level in range(0, max_zoom_level + 1):
    cog_translate(
        r"D:\组内项目\DGGS-Cube计算优化\DGGS\data\cogtest_2_different_landsat\landsat_a.tif",
        r"D:\组内项目\DGGS-Cube计算优化\DGGS\data\cogtest_2_different_landsat\landsat_a_4326_" + str(
            zoom_level) + ".tif",
        cog_profile,
        web_optimized=True,
        tms=morecantile.tms.get("WGS1984Quad"),
        # https://github.com/developmentseed/morecantile?tab=readme-ov-file#defaults-grids
        overview_level=0,  # 概览级别
        zoom_level=zoom_level,  # 缩放级别
        # aligned_levels=4, # 与几个层级对齐
        # additional_cog_metadata={
        #     "rhealpix:tile_format": "rHEALPix",
        # },
    )
