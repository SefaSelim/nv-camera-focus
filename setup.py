import setuptools

setuptools.setup(
    name="camerafocus",
    version="0.0.1",
    author="DigiNova",
    author_email='info@diginova.com.tr',
    description="Camera Focus",
    url='https://github.com/novavision-ai/camerafocus',
    license='MIT',
    install_requires=['sdk', 'opencv-python-headless', 'numpy', 'requests', 'onvif-zeep'],

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],

    packages=[
        'novavision.camerafocus',
        'novavision.camerafocus.classes',
        'novavision.camerafocus.configs',
        'novavision.camerafocus.executors',
        'novavision.camerafocus.models',
        'novavision.camerafocus.utils'
    ],
    package_dir={'novavision.camerafocus': 'src'},
    python_requires=">=3.6"
)
