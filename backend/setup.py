from setuptools import find_packages, setup


setup(
    name="poker-sim",
    version="0.1.0",
    description="Local 6-max no-limit hold'em simulator with heuristic bots",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.9",
    install_requires=[
        "fastapi>=0.115.0",
        "uvicorn[standard]>=0.30.0",
    ],
)
