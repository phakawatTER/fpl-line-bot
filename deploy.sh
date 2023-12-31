#!/bin/bash

mkdir deployment_package
mkdir -p layer/python/lib/python3.9/site-packages
mkdir -p layer_plot_generator/python/lib/python3.9/site-packages
cp requirement.txt requirement.deploy.txt
cp requirement.plot_generator.txt requirement.deploy2.txt

cp -rf app deployment_package
cp -rf database deployment_package
cp -rf api deployment_package
cp -rf adapter deployment_package
cp -rf config deployment_package
cp -rf lambda deployment_package
cp -rf line deployment_package
cp -rf models deployment_package
cp -rf models deployment_package
cp -rf plot deployment_package
cp -rf services deployment_package
cp -rf util deployment_package



# List of dependencies to remove
dependencies_to_remove=("matplotlib" "numpy" "kiwiresolver" "Pillow" "firebase-admin")

# general lambdas dependencies
# remove unused dependencies
source remove_dependencies.sh requirement.deploy.txt matplotlib numpy kiwiresolver Pillow firebase-admin
pip install -r requirement.deploy.txt -t layer/python/lib/python3.9/site-packages
pip install firebase-admin --no-deps -t layer/python/lib/python3.9/site-packages

# plot generator dependencies
source remove_dependencies.sh requirement.deploy2.txt matplotlib numpy kiwiresolver Pillow firebase-admin
pip install -r requirement.deploy2.txt -t layer_plot_generator/python/lib/python3.9/site-packages

# build numpy@1.26.2
curl -O https://files.pythonhosted.org/packages/2f/75/f007cc0e6a373207818bef17f463d3305e9dd380a70db0e523e7660bf21f/numpy-1.26.2-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
unzip -o numpy-1.26.2-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl -d ./layer_plot_generator/python/lib/python3.9/site-packages/
rm numpy-1.26.2-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl

# build matplotlib@3.8.2
curl -O https://files.pythonhosted.org/packages/53/1f/653d60d2ec81a6095fa3e571cf2de57742bab8a51a5c01de26730ce3dc53/matplotlib-3.8.2-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
unzip -o matplotlib-3.8.2-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl -d ./layer_plot_generator/python/lib/python3.9/site-packages/
rm matplotlib-3.8.2-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl

# build PIL@10.1.0
curl -O https://files.pythonhosted.org/packages/9f/3a/ada56d489446dbb7679d242bfd7bb159cee8a7989c34dd34045103d5280d/Pillow-10.1.0-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
unzip -o Pillow-10.1.0-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl -d ./layer_plot_generator/python/lib/python3.9/site-packages/
rm Pillow-10.1.0-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl

# build kiwisolver@1.4.5
curl -O https://files.pythonhosted.org/packages/c0/a8/841594f11d0b88d8aeb26991bc4dac38baa909dc58d0c4262a4f7893bcbf/kiwisolver-1.4.5-cp39-cp39-manylinux_2_12_x86_64.manylinux2010_x86_64.whl
unzip -o kiwisolver-1.4.5-cp39-cp39-manylinux_2_12_x86_64.manylinux2010_x86_64.whl -d ./layer_plot_generator/python/lib/python3.9/site-packages/
rm kiwisolver-1.4.5-cp39-cp39-manylinux_2_12_x86_64.manylinux2010_x86_64.whl


random_string=$(date +'%Y%m%d%H%M%S')
echo "$random_string" > version.txt
mv version.txt deployment_package

aws s3 cp config.json s3://ds-fpl/config.json
aws s3 cp service_account.json s3://ds-fpl/service_account.json

sam package --debug --template template.yml  --s3-bucket ds-fpl \
--s3-prefix "cloudformation-package" \
--output-template-file template-export.yml

sam deploy \
--template-file template-export.yml \
--stack-name fpl-line-message-api \
--capabilities CAPABILITY_NAMED_IAM

# clean up deployment files
rm -rf deployment_package
rm -rf layer
rm -rf layer_plot_generator
rm requirement.deploy.txt
rm requirement.deploy2.txt
rm template-export.yml
