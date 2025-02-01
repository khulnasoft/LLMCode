from setuptools import find_packages, setup

setup(
    name="llmcode-install",
    version="0.0.1",
    packages=find_packages(),
    description="Installer for the llmcode AI pair programming CLI tool.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Md Sulaiman",
    author_email="dev.sulaiman@icloud.com",
    url="https://github.com/khulnasoft/llmcode",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "uv>=0.5.0",
    ],
    entry_points={
        "console_scripts": [
            "llmcode-install=llmcode_install.main:install_llmcode",
        ],
    },
)
