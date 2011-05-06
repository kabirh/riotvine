---------------
AUDIENCE
---------------

Experience administering a Unix-like system is assumed in the instructions below.

--------------------------
APPLICATION REQUIREMENTS
--------------------------

- A Solaris, OpenSolaris, FreeBSD, Linux, or Mac OSX based server. We do not recommend the Windows server platforms.
- Python 2.5+
- Postgresql 8.2
- Django: 1.0.X branch as of March 15, 2009 or better.
- Psycopg2: 2.0.7+
- PyCaptcha: http://svn.navi.cx/misc/trunk/pycaptcha/
- PIL: 1.1.6
- Postfix SMTP server: any recent version is fine.
- FckEditor: 2.6.4
- Recommended: Memcached and PyMemcached (any recent version as of September 2008)
- django-messages:
	http://django-messages.googlecode.com/svn/trunk/ (SVN rev. 72)
- SSL certificate for the production domain http://illiusrock.com (self-signed certificates may be used for your test and preview domains, if you prefer.)

--------------------
INSTALLATION
--------------------

- First install all of the above dependencies following their respective installation documentation (you can install Django and django-messages globally or install them in the site-packages directory mentioned below).

- Decide on the user home directory (default/recommended directory is: /home/illiusrock) where you intend to install the Illius Rock web application.

- cd /home/illiusrock

- mkdir site-packages

- mkdir bin

- mkdir backups

- If you haven't installed Django and django-messages globally, install them now under /home/site-packages/django and /home/site-packages/tpl/messages respectively. Here, tpl stands for Third Party Libraries.

- Install the Illius Rock web app under /home/illiusrock/site-packages/irock. Installation consists of simply copying the source tree straight into /home/illiusrock/site-packages/irock

- Under /home/illiusrock/site-packages/irock/deployment/, you will find several shell scripts:
	- beta-irock.sh -> start the main web application
	- beta-queue.sh -> start the queue service required for campaign management
	- backup.sh -> backup the database. Schedule this through cron to generate periodic backups. The backups will be generated in the /home/illiusrock/backups directory.
	- syncdb.sh -> Create database for the application
	- load-initial-data.sh -> Load initial data (flatpages, etc.)
	- session-cleanup.sh -> Periodic clean up of expired session data. Schedule this to run once a day through cron.
	
- There's a second set of these scripts for the preview server. They are under 
/home/illiusrock/site-packages/irock/deployment/preview

- Create the database tables and indexes required by the Django app by executing the script syncdb.sh

- Load initial data (such as flatpages) by executing the script: load-initial-data.sh

- Set up the nginx web server using the nginx.conf provided under the deployment sub-directory. This sets nginx up to proxy-forward Django requests to port 8000 on the localhost. This may be tweaked to use multiple proxy ports as necessary.

- Ensure that the Postgresql server, memcached server, and postfix server have been started.

- Start the nginx web server.

- Start the web application by running the scripts beta-irock.sh and beta-queue.sh. Note that these scripts start server applications. As such they do not return.

- Verify that the application is running by browsing to the IR homepage.

- *.fmri files are provided for relevant scripts so that they can be installed as OS services on the Solaris platform (i.e. Joyent's Accelerator servers.) It's recommended that you install and use these FRMI/SMF based services in lieu of directly executing the above mentioned shell scripts. This is because SMF makes it much easier to start, stop, and monitor these long running applications.

- We have fully deployed the application on your two Joyent Accelerator servers: Beta and Preview. We will also assist in full deployment of the final site at http://illiusrock.com. After that point, we can assist in any future deployments of the application at a low hourly rate.

-----------
ADMIN
-----------

- The web-based admin area for the Illius Rock application (IR web app) is available at https://xyz.illiusrock.com/admin/ where xyz is either beta or preview (or nothing) depending on the instance being administered.

- Log in to the admin to gain access to the database for the various modules built in to the IR web app.

- All open administrative tasks (such as campaign approval requests, ticket requests, etc.) are all shown in the Queue -> ActionItems area. Closed tasks are also shown there.

- Piermont Web, Inc. is happy to offer three free-of-cost training sessions on how to use the Admin area to accomplish your IR Campaign and general application management workflow. Please contact us whenever you or your staff would like to undergo a training session. We can provide additional training sessions at a low hourly rate. Note that these training sessions do not include administrative training for your server's operating system maintenance, nor do they include training on installation of the above software. They are meant for your staff that will be using the web app's admin area to perform day-to-day IR campaign and content management activities.

-----------------
CUSTOMIZATION
-----------------

- All web app specific settings are listed in the file /home/illiusrock/site-packages/irock/irock/custom_settings.py. If a setting is changed, the web applications (beta-irock and beta-queue) need to be restarted.


--------------------
IF THINGS GO WRONG
---------------------

Contact us!

Piermont Web, Inc. is committed to providing you with complete support for the code we've delivered. We will fix all future bugs in the code built by us without additional charges. We will also fix free-of-cost any problems with the  app installations that we were responsible for deploying for you (beta, preview, and final instances.)

--------------------
SCALABILITY
--------------------

Your web app code is designed to scale up to use all the hardware you can throw at it. Ultimately, once the site gets hundreds of simultaneous visitors, you will need to upgrade your server's capacity (CPU, memory, disk space, and bandwidth.) In most cases, the application will not have to be modified to take advantage of these upgraded resources.

---------------------
EXTENSIBILITY
---------------------

All web app code is built in a modular and extensible fashion. Every module includes detailed inline comments to make the code easy to understand for a new developer. You are welcome to contact Piermont Web, Inc. or another qualified Django developer when you need to extend the features of your application.

=====================

