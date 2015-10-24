import setuptools

setuptools.setup(
    name = 'route53dynamicdns',
    version = '1.0.0dev',
    packages = setuptools.find_packages(),
    entry_points = {'console_scripts': ['route53dynamicdns = route53dynamicdns.__main__:main']},
    install_requires = ['boto3'],
)
