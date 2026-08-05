import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'scout_gas'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Scout2Map',
    maintainer_email='Scout2Map@users.noreply.github.com',
    description='Simulated gas sensor and hexagonal gas-risk event map for Scout2Map',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'gas_sensor_node = scout_gas.gas_sensor_node:main',
        ],
    },
)
