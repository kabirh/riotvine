#!/bin/bash
python ./compileproject.py
ant -f ant-tgz.xml
scp dist/ir-deploy.tgz illiusrock@ir2:./downloads/.

ssh illiusrock@ir2 ./site-packages/redeploy.sh

ssh admin@ir2

