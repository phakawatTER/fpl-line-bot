#!/bin/bash

mkdir deployment_package
mkdir -p layer/python/lib

cp -rf api deployment_package
cp -rf adapter deployment_package
cp -rf config deployment_package
cp -rf lambda deployment_package
cp -rf line deployment_package
cp -rf models deployment_package
cp -rf models deployment_package
cp -rf services deployment_package
cp -rf util deployment_package

cp -rf env_fpl/lib layer/python

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

rm -rf deployment_package
rm -rf layer
