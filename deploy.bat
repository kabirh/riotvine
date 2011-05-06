#!/bin/bash
python ./compileproject.py

ant -f ant-tgz.xml
scp dist/ir-deploy.tgz illiusrock@ir:./downloads/.
#scp dist/ir-deploy.tgz illiusrock@ir2:./downloads/.

ssh illiusrock@ir ./site-packages/redeploy.sh

ssh admin@ir

