from setuptools import setup, find_packages

setup(
    name='paypal-subscription',
    version='0.1.1',
    packages=find_packages(),
    author='Codeat',
    author_email='mte90net@gmail.com',
    description='This Python library allows you to interact with the PayPal REST API to manage subscriptions with variable pricing. It includes functionality for creating, updating, suspend and verifying subscriptions, as well as managing products and plans.',
    long_description=open('readme.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/CodeAtCode/paypal-subscription-lib',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.11',
)
