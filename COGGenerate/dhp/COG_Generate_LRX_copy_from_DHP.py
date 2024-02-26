# -*- coding: utf-8 -*-
import glob
import os
import time
from multiprocessing import Pool, cpu_count
from concurrent.futures import ThreadPoolExecutor

from osgeo import gdal, osr


# os.environ['PROJ_LIB'] = '/home/geocube/anaconda3/envs/oge/share/proj/'
# os.environ['GDAL_DATA'] = '/home/geocube/anaconda3/envs/oge/share/'

def translate_to_COG(in_ds, outputPath, tilesize):
    """
    将dataset转为Cloud-Optimized GeoTIFF (COG)文件。

    参数：
    in_ds (gdal.Dataset): 输入的GDAL数据集。
    outputPath (str): 输出的COG文件路径。
    tilesize (int): COG文件的瓦片大小。

    返回：
    无返回值。

    注意：
    - 该函数首先获取输入影像的波段信息，并计算出合适的金字塔层级（maxLevel）和2倍下采样的层级（levels）。
    - 然后将输入数据集转换为Cloud-Optimized GeoTIFF格式，并保存为输出文件。
    - 最后可选地删除一些不必要的.ovr和.aux.xml文件。
    """

    im_bands = in_ds.RasterCount
    for i in range(im_bands):
        # 获取nodata和波段统计值
        nodataVal = in_ds.GetRasterBand(i + 1).GetNoDataValue()
        maxBandValue = in_ds.GetRasterBand(i + 1).GetMaximum()
        # 缺啥设置啥
        if maxBandValue is None:
            in_ds.GetRasterBand(i + 1).ComputeStatistics(0)
        if nodataVal is None:
            in_ds.GetRasterBand(i + 1).SetNoDataValue(0.0)

    # 额外要求，为了使得金字塔缩放后的图像宽度或高度大于或等于切片宽度（高度），maxlevel有如下约束
    # 例如源图像1667*1667，tilesize=256,那么1667/256=6.52->6。故maxlevel即为6
    if in_ds.RasterXSize >= in_ds.RasterYSize:
        maxLevel = int(in_ds.RasterYSize / tilesize)
    elif in_ds.RasterXSize <= in_ds.RasterYSize:
        maxLevel = int(in_ds.RasterXSize / tilesize)

    # 判断maxlevel是否为偶数，不是则减1
    if maxLevel & 1 == 0:
        maxLevel = maxLevel
    else:
        maxLevel = maxLevel - 1

    # 计算2倍下采样的层级，2,4,8,16这类
    levels = []
    i = 1
    level = 2
    while level < maxLevel + 1:
        levels.append(level)
        i = i + 1
        level = 2 ** i

    driver = gdal.GetDriverByName('GTiff')

    num_overviews = in_ds.GetRasterBand(1).GetOverviewCount()
    # 如果源文件已有overview,则先删除这些overviews,删除方法为重新生成一张tmp.tif。后面生成最终结果再删除tmp.tif
    if num_overviews > 0:
        tmp_outputPath = outputPath.replace('.tif', '_tmp.tif')

        # 使用gdal_translate转换COG为普通的GeoTIFF
        # 'COPY_SRC_OVERVIEWS' 设置为 'NO' 来移除概览图
        # 其他选项可以保持默认，以保留原始图像的其他信息
        gdal.Translate(tmp_outputPath, in_ds, format='GTiff', creationOptions=['TILED=NO', 'COPY_SRC_OVERVIEWS=NO'])

        in_ds_new = get_tif_dataset(tmp_outputPath)
        in_ds_new.BuildOverviews("NEAREST", levels)  # 例如in_ds.BuildOverviews("NEAREST", [2, 4, 8, 16]) 2阶幂
        # BuildOverviews("NEAREST/AVERAGE/CUBIC", [x1, x2, x3, x4, x5，xn为levels,即缩放的程度])

        block_x_size = "BLOCKXSIZE=" + str(tilesize)
        block_y_size = "BLOCKYSIZE=" + str(tilesize)

        # 可以加上“COMPRESS=DEFLATE/LZW”来对图像进行压缩
        driver.CreateCopy(outputPath, in_ds_new,
                          options=["COPY_SRC_OVERVIEWS=YES",
                                   "TILED=YES",
                                   "INTERLEAVE=BAND",
                                   block_x_size,
                                   block_y_size])

        in_ds_new = None
        if os.path.exists(tmp_outputPath + ".ovr"):
            os.remove(tmp_outputPath + ".ovr")
        if os.path.exists(tmp_outputPath + ".aux.xml"):
            os.remove(tmp_outputPath + ".aux.xml")
        if os.path.exists(tmp_outputPath):
            os.remove(tmp_outputPath)

    # 没有overview就直接生成
    else:
        in_ds.BuildOverviews("NEAREST", levels)  # 例如in_ds.BuildOverviews("NEAREST", [2, 4, 8, 16]) 2阶幂
        # BuildOverviews("NEAREST/AVERAGE/CUBIC", [x1, x2, x3, x4, x5，xn为levels,即缩放的程度])

        block_x_size = "BLOCKXSIZE=" + str(tilesize)
        block_y_size = "BLOCKYSIZE=" + str(tilesize)

        # 可以加上“COMPRESS=DEFLATE/LZW”来对图像进行压缩
        driver.CreateCopy(outputPath, in_ds,
                          options=["COPY_SRC_OVERVIEWS=YES",
                                   "TILED=YES",
                                   "INTERLEAVE=BAND",
                                   block_x_size,
                                   block_y_size])

        # driver.CreateCopy(outputPath, in_ds)


def warp_dataset(in_ds, proj, resampling=1):
    """
    转换空间参考

    参数：
    in_ds (gdal.Dataset): 输入的GDAL数据集。
    proj (str): 目标空间参考的WKT格式字符串。
    resampling (int): 重采样方法的索引值，默认为1（Bilinear）。

    返回：
    warped_ds (gdal.Dataset): 转换后的GDAL数据集。

    注意：
    - 该函数将输入的GDAL数据集根据目标空间参考进行空间参考转换，并返回转换后的GDAL数据集。
    """

    RESAMPLING_MODEL = ['', gdal.GRA_NearestNeighbour,
                        gdal.GRA_Bilinear, gdal.GRA_Cubic]

    resampleAlg = RESAMPLING_MODEL[resampling]

    return gdal.AutoCreateWarpedVRT(in_ds, None, proj, resampleAlg)


def get_tif_dataset(fileDir, srid=None):
    """
    返回tif文件dataset

    参数：
    fileDir (str): 文件路径。
    srid (int): EPSG SRID，若指定且不同于数据集的空间参考，则将数据集转换为该空间参考。

    返回：
    dataset (gdal.Dataset): 文件对应的GDAL数据集。

    注意：
    - 该函数打开指定路径的文件，并返回对应的GDAL数据集。
    - 如果提供了目标空间参考（srid），且数据集的空间参考与目标空间参考不同，将进行空间参考转换。
    """

    dataset = gdal.Open(fileDir, gdal.GA_ReadOnly)
    if dataset is None:
        print(fileDir + "文件无法打开")
        return

    fileSrs = osr.SpatialReference()

    fileSrs.ImportFromWkt(dataset.GetProjection())

    if srid is None:
        return dataset
    else:
        outSrs = osr.SpatialReference()
        outSrs.ImportFromEPSG(srid)

        if fileSrs.IsSame(outSrs):
            return dataset
        else:
            return warp_dataset(dataset, outSrs.ExportToWkt())


def convert_to_COG(input_path, output_path):
    """
    其他格式文件转COG，目前可以支持geotiff, netCDF。

    参数：
    input_path (str): 输入文件的路径。
    output_path (str): 输出文件的路径。

    返回：
    无返回值。

    注意：
    - 该函数将输入文件转换为Cloud-Optimized GeoTIFF格式，并保存为输出文件。
    - 如果输出文件所在的文件夹不存在，则会自动创建。
    - 如果转换过程中出现异常，会打印错误信息和有问题的文件路径。
    - 最后，函数会删除一些不必要的.ovr和.aux.xml文件。
    """

    # 记个教训，像这种China_Geodetic_Coordinate_System_2000_Transverse_Mercator，自定义的，未在EPSG
    # 中编号的，下次要先进行预处理转坐标系才行，否则无法进行下一步操作
    # 如果没有该文件夹则创建
    folder_path = os.path.dirname(output_path)
    if not os.path.exists(folder_path):
        # 如果不存在，则创建一系列文件夹
        os.makedirs(folder_path)
        print(f"文件夹已创建：{folder_path}")
    else:
        print("文件夹已存在。")

    # 开始转COG
    try:
        # 获取影像数据集
        originDataset = get_tif_dataset(input_path, 4326)
        # getTifDataset(inPath,4326),这种方式对于正弦投影不好,可以考虑用这个函数SinusoidalProject_to_epsg4326

        # 转换成COG
        translate_to_COG(originDataset, output_path, 256)
    except Exception as e:
        print('transform error:', e)
        print('有问题的文件为:', input_path)
    else:
        # 最后清空数据集
        del originDataset

        # 可选,删除一些不必要的.ovr和.aux.xml文件
        if os.path.exists(input_path + ".ovr"):
            os.remove(input_path + ".ovr")
        if os.path.exists(input_path + ".aux.xml"):
            os.remove(input_path + ".aux.xml")

        # if os.path.exists(tmp_4326):
        #     os.remove(tmp_4326)
        # if os.path.exists(tmp_4326 + ".ovr"):
        #     os.remove(tmp_4326 + ".ovr")
        # if os.path.exists(tmp_4326 + ".aux.xml"):
        #     os.remove(tmp_4326 + ".aux.xml")


def convert_to_COG_pool(tuple_data):
    """
    多线程版本的其他格式文件转COG，目前支持geotiff和netCDF格式的转换。

    参数：
    tuple_data (tuple): 输入文件路径和输出文件路径组成的元组。

    返回：
    无返回值。

    注意：
    - 该函数是其他格式文件转COG的多线程版本，用于在多线程环境下进行文件转换。
    - 接收一个包含输入文件路径和输出文件路径的元组作为参数。
    - 如果输出文件所在的文件夹不存在，则会自动创建。
    - 如果转换过程中出现异常，会打印错误信息和有问题的文件路径。
    - 最后，函数会删除一些不必要的.ovr和.aux.xml文件。
    """

    input_path, output_path = tuple_data
    # 如果没有该文件夹则创建
    folder_path = os.path.dirname(output_path)
    if not os.path.exists(folder_path):
        # 如果不存在，则创建一系列文件夹
        os.makedirs(folder_path)
        print(f"文件夹已创建：{folder_path}")
    else:
        print("文件夹已存在。")

    # 开始转COG
    try:
        # 获取影像数据集
        originDataset = get_tif_dataset(input_path)  # getTifDataset(inPath, 4326)

        # 转换成COG
        translate_to_COG(originDataset, output_path, 256)
    except Exception as e:
        print('transform error:', e)
        print('有问题的文件为:', input_path)
    else:
        # 最后清空数据集
        del originDataset

        # 可选,删除一些不必要的.ovr和.aux.xml文件
        if os.path.exists(input_path + ".ovr"):
            os.remove(input_path + ".ovr")
        if os.path.exists(input_path + ".aux.xml"):
            os.remove(input_path + ".aux.xml")


def get_output_path(file_path_tmp, output_path):
    """
    根据输入文件的路径获取输出文件的路径。

    参数：
    file_path_tmp (str): 输入的文件路径。
    output_path (str): 输出的文件夹路径。

    返回：
    output_file (str): 经过封装后的输出文件路径。

    注意：
    - 该函数从输入文件路径中获取文件名，然后将输出文件夹路径与文件名拼接得到输出文件的路径。
    """
    file_name = os.path.basename(file_path_tmp)
    output_file = os.path.join(output_path, file_name)
    return output_file


if __name__ == '__main__':
    gdal.AllRegister()
    # gdal的版本最好高一点，实时更新，目前是gdal 3.3.3
    start = time.time()

    # 输入路径
    input_path = r'C:\Users\dell\Desktop\GLASS\FAPAR\GLASS-tile'
    # 输出路径
    output_path = r'C:\Users\dell\Desktop\GLASS\FAPAR\COG'

    # 单幅影像
    if os.path.isfile(input_path):
        convert_to_COG(input_path, output_path)
    # 单个文件夹下多幅影像
    elif os.path.isdir(input_path):
        file_list = []
        for root, dirs, files in os.walk(input_path):
            for file in files:
                file_path_tmp = os.path.join(root, file)
                if ".tif" in file_path_tmp and "xml" not in file_path_tmp and "ovr" not in file_path_tmp and "tmp" not in file_path_tmp:
                    output_file = file_path_tmp.replace("GLASS-tile", "COG")
                    if os.path.exists(output_file) == False:  # 如果已经生成了，则跳过
                        tuple = (file_path_tmp, output_file)
                        file_list.append(tuple)
        file_list.sort()
        # 这里采用pool利用多进程实现，要稍微改造下convert_to_COG为convert_to_COG_pool

        with Pool(15) as p:
            p.map(convert_to_COG_pool, file_list)

        # for file in file_list:
        #     convert_to_COG(file)

    else:
        print(input_path + " : 路径既不是文件也不是文件夹")

    end = time.time()
    print('Running time: %s Seconds' % (end - start))
