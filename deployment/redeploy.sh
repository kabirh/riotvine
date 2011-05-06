#!/bin/bash
export PATH=/opt/local/bin:$PATH

cd ~/site-packages

if [ -e "$HOME/downloads/ir-deploy.tgz" ]; then
	gtar -xzf ~/downloads/ir-deploy.tgz
	echo "Deployment done. Please restart *-irock and *-queue services."
else
	echo "Nothing to deploy"
fi
