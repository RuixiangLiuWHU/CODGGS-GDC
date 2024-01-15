from COGGenerate.COG_Translate import cog_translate
import morecantile

cog_profile = {
    "driver": "GTiff",
    "interleave": "pixel",
    "tiled": True,
    "blockxsize": 256,
    "blockysize": 256,
    "compress": "NONE",
}
cog_translate(
    r"D:\组内项目\DGGS\data\cogtest\a_clip_small_small.tif",
    r"D:\组内项目\DGGS\data\cogtest\a_clip_small_small_cogeo.tif",
    cog_profile,
    web_optimized=True,
    tms=morecantile.tms.get("WGS1984Quad"),
)

# print(morecantile.tms.get("WebMercatorQuad"))
