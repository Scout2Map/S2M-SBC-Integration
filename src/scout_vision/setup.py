from glob import glob
import os

from setuptools import find_packages, setup


package_name = 'scout_vision'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md']),
        (os.path.join('share', package_name, 'launch'),
         glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'),
         glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Scout2Map',
    maintainer_email='Scout2Map@users.noreply.github.com',
    description='YOLOv8 ONNX vision wrapper for Scout2Map',
    license='Apache-2.0',
    extras_require={
        'test': ['pytest'],
    },
    entry_points={
        'console_scripts': [
            'vision_node = scout_vision.vision_node:main',
        ],
    },
)
