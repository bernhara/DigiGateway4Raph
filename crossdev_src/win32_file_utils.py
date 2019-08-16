

import win32file
import os
from common.path_utils import get_base_dir
import sys


def total_blocks():
    '''
    Return the total number of blocks remaining.
    '''
    if sys.platform == "win32":
        sectPerCluster, bytesPerSector, freeClusters, totalClusters = win32file.GetDiskFreeSpace(get_base_dir())
        return totalClusters
    else:
        return os.statvfs(get_base_dir()).f_blocks


def blocks_remaining():
    '''
    Return the total number of blocks available.
    '''
    if sys.platform == "win32":
        sectPerCluster, bytesPerSector, freeClusters, totalClusters = win32file.GetDiskFreeSpace(get_base_dir())
        return freeClusters
    else:
        return os.statvfs(get_base_dir()).f_bavail


def total_bytes():
    '''
    Return the size of the file system in bytes.
    '''
    if sys.platform == "win32":
        sectPerCluster, bytesPerSector, freeClusters, totalClusters = win32file.GetDiskFreeSpace(get_base_dir())
        return sectPerCluster * bytesPerSector * totalClusters
    else:
        stats = os.statvfs(get_base_dir())
        return stats.f_frsize * stats.f_blocks


def bytes_remaining():
    '''
    Return the number of bytes available on the system.
    '''
    if sys.platform == "win32":
        sectPerCluster, bytesPerSector, freeClusters, totalClusters = win32file.GetDiskFreeSpace(get_base_dir())
        return sectPerCluster * bytesPerSector * totalClusters
    else:
        stats = os.statvfs(get_base_dir())
        return stats.f_frsize * stats.f_bavail


def percent_remaining():
    '''
    Return the percent (as a number between 0 and 1)
    available for writing on the file system.
    '''
    if sys.platform == "win32":
        return 1.0
        # simulated
        sectPerCluster, bytesPerSector, freeClusters, totalClusters = win32file.GetDiskFreeSpace(get_base_dir())
        return sectPerCluster * bytesPerSector * totalClusters
    else:
        stats = os.statvfs(get_base_dir())
        return 1.0 * stats.f_bavail / stats.f_blocks


def percent_used():
    '''
    Return the percent (as a number between 0 and 1)
    of the blocks currently used.
    '''
    return 1.0 - percent_remaining()


if __name__ == '__main__':
    pass