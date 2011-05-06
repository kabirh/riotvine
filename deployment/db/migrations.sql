/*
-- Deployed May 25, 2010
BEGIN;
ALTER TABLE "event_event" ADD COLUMN "has_unlock" boolean default FALSE;
ALTER TABLE "event_event" ADD COLUMN "unlock_subject" varchar(50) default '';
ALTER TABLE "event_event" ADD COLUMN "unlock_body" text default '';
ALTER TABLE "event_event" ADD COLUMN "unlock_type" varchar(25) default '';
ALTER TABLE "event_event" ADD COLUMN "unlock_link" varchar(200) default '';
COMMIT;

BEGIN;
CREATE INDEX "event_event_has_unlock" ON "event_event" ("has_unlock");
COMMIT;
*/

/*
-- Deployed May 22, 2010
BEGIN;
ALTER TABLE registration_userprofile ADD COLUMN fsq_userid character varying(64) default '';
ALTER TABLE twitter_twitterprofile ADD COLUMN screen_name_lower character varying(32) default '';
COMMIT;

BEGIN;
CREATE INDEX "registration_userprofile_fsq_userid" ON "registration_userprofile" ("fsq_userid");
CREATE INDEX "twitter_twitterprofile_screen_name_lower" ON "twitter_twitterprofile" ("screen_name_lower");
COMMIT;
*/

/*
-- Deployed May 17, 2010
BEGIN;
ALTER TABLE registration_userprofile ADD COLUMN full_artistname character varying(200) default '';
COMMIT;

BEGIN;
CREATE INDEX "registration_userprofile_full_artistname" ON "registration_userprofile" ("full_artistname");
COMMIT;
*/

/*
-- Deployed April 2, 2010
BEGIN;
ALTER TABLE registration_userprofile ADD COLUMN fb_session_key character varying(250) default '';
COMMIT;

BEGIN;
CREATE INDEX "registration_userprofile_fb_session_key" ON "registration_userprofile" ("fb_session_key");
COMMIT;
*/

/*
-- Deployed March 15, 2010
BEGIN;
ALTER TABLE event_venue ADD COLUMN fsq_m integer default 0;
ALTER TABLE event_venue ADD COLUMN fsq_f integer default 0;
ALTER TABLE event_venue ADD COLUMN fsq_mf numeric(10,2) default 0 null;
ALTER TABLE event_venue ADD COLUMN fsq_fm numeric(10,2) default 0 null;
COMMIT;

BEGIN;
CREATE INDEX "event_venue_fsq_m" ON "event_venue" ("fsq_m");
CREATE INDEX "event_venue_fsq_f" ON "event_venue" ("fsq_f");
CREATE INDEX "event_venue_fsq_mf" ON "event_venue" ("fsq_mf");
CREATE INDEX "event_venue_fsq_fm" ON "event_venue" ("fsq_fm");
COMMIT;
*/

/*
-- Deployed March 16, 2010
BEGIN;
ALTER TABLE event_venue ADD COLUMN fsq_ratio character varying(25) default '';
COMMIT;

BEGIN;
CREATE INDEX "event_venue_fsq_ratio" ON "event_venue" ("fsq_ratio");
COMMIT;
*/

/*
-- Deployed March 14, 2010
BEGIN;
ALTER TABLE event_venue ADD COLUMN fsq_id character varying(64) default '';
ALTER TABLE event_venue ADD COLUMN fsq_checkins integer default 0;
COMMIT;

BEGIN;
CREATE INDEX "event_venue_fsq_id" ON "event_venue" ("fsq_id");
CREATE INDEX "event_venue_fsq_checkins" ON "event_venue" ("fsq_checkins");
COMMIT;
*/

/*
-- Deployed March 1, 2010
BEGIN;
ALTER TABLE registration_userprofile ADD COLUMN permission character varying(30) default 'everyone';
UPDATE registration_userprofile SET permission='everyone';
COMMIT;
*/

/*
-- Deployed Feb 25, 2010
from event.models import Event

ex = Event.objects.active()

for e in ex:
	e.recompute()

print ex.count()

*/
/*
-- Deployed: Feb 21, 2010
BEGIN;
ALTER TABLE event_event ADD COLUMN ext_event_id character varying(50) default '';
ALTER TABLE event_event ADD COLUMN ext_event_source character varying(50) default '';
ALTER TABLE event_event ADD COLUMN has_image boolean default TRUE;
COMMIT;

BEGIN;
UPDATE event_event SET ext_event_id='', ext_event_source='';
CREATE INDEX "event_event_ext_event_id" ON "event_event" ("ext_event_id");
CREATE INDEX "event_event_ext_event_source" ON "event_event" ("ext_event_source");
CREATE INDEX "event_event_ext_event_has_image" ON "event_event" ("has_image");
COMMIT;
*/

/*
-- Deployed: Feb 21, 2010
BEGIN;
ALTER TABLE registration_userprofile ADD COLUMN activation_code character varying(40) default '';
ALTER TABLE registration_userprofile ADD COLUMN is_verified boolean default FALSE;
COMMIT;

BEGIN;
UPDATE registration_userprofile SET is_verified=TRUE, activation_code='';
CREATE INDEX "registration_userprofile_activation_code" ON "registration_userprofile" ("activation_code");
COMMIT;
*/

/*
-- Deployed: Feb 3, 2010
BEGIN;
ALTER TABLE event_event ADD COLUMN max_tweets integer default 0;
COMMIT;
*/

/*
-- Deployed: Jan 18, 2010
BEGIN;
-- ALTER TABLE registration_userprofile ADD COLUMN fb_suggested_sig character varying(40) default '';
ALTER TABLE registration_userprofile ADD COLUMN send_favorites boolean default TRUE;
COMMIT;
*/

/*
-- Deployed: Dec 10, 2009
BEGIN;
ALTER TABLE auth_user ALTER email TYPE character varying(150);
ALTER TABLE registration_userprofile ADD COLUMN fb_userid character varying(32) default '';
COMMIT;

BEGIN;
CREATE INDEX "registration_userprofile_fb_userid" ON "registration_userprofile" ("fb_userid");
COMMIT;
*/

/*
-- Deployed: Dec 5, 2009
BEGIN;
ALTER TABLE event_stats ADD COLUMN num_owner_views integer default 0;
COMMIT;

BEGIN;
CREATE INDEX "event_stats_num_owner_views" ON "event_stats" ("num_owner_views");
COMMIT;

BEGIN;
ALTER TABLE event_event ADD COLUMN uuid character varying(40) default '';
COMMIT;

BEGIN;
CREATE INDEX "event_event_uuid" ON "event_event" ("uuid");
COMMIT;

*/

/*
-- Deployed: Nov 17, 2009
BEGIN;
ALTER TABLE event_event ADD COLUMN headliner character varying(200) default '';
ALTER TABLE event_event ADD COLUMN artists character varying(250) default '';
ALTER TABLE event_event ADD COLUMN aws_asins character varying(250) default '';
COMMIT;

BEGIN;
CREATE INDEX "event_event_headliner" ON "event_event" ("headliner");
COMMIT;
*/

/*
-- Deployed: Nov 13, 2009
BEGIN;
ALTER TABLE event_event ADD COLUMN is_free boolean default FALSE;
COMMIT;

BEGIN;
CREATE INDEX "event_event_is_free" ON "event_event" ("is_free");
CREATE INDEX "event_venue_alias" ON "event_venue" ("alias");
COMMIT;
*/

/*
-- Deployed: Nov 7, 2009

BEGIN;
ALTER TABLE event_event ADD COLUMN tm_url character varying(750) default '';
COMMIT;

BEGIN;
CREATE INDEX "event_event_tm_url" ON "event_event" ("tm_url");
COMMIT;
*/

/*
BEGIN;
ALTER TABLE event_event ADD COLUMN bg_tile boolean default FALSE;
ALTER TABLE event_event ADD COLUMN bg_image character varying(250) default '';
ALTER TABLE event_event ADD COLUMN bg_width integer default 0;
ALTER TABLE event_event ADD COLUMN bg_height integer default 0;
COMMIT;
*/

/*
BEGIN;
ALTER TABLE registration_userprofile ADD COLUMN is_sso boolean default FALSE;
ALTER TABLE registration_userprofile ADD COLUMN sso_username character varying(32) default '';
COMMIT;

BEGIN;
CREATE INDEX "registration_userprofile_is_sso" ON "registration_userprofile" ("is_sso");
CREATE INDEX "registration_userprofile_sso_username" ON "registration_userprofile" ("sso_username");
COMMIT;
*/

/*
BEGIN;

ALTER TABLE registration_userprofile ADD COLUMN send_reminders boolean default TRUE;

COMMIT;
*/

/*
BEGIN;

ALTER TABLE event_event ADD COLUMN lastfm_id character varying(50) UNIQUE;
ALTER TABLE event_event ADD COLUMN lastfm_venue_url character varying(200) default '';
CREATE INDEX "event_event_lastfm_venue_url" ON "event_event" ("lastfm_venue_url");

COMMIT;
*/

/* DEPLOYED - June 15, 2009
After deployment:
    - Resave all events and campaigns so that badges are regenerated.

python manage.pyc shell
from campaign.models import Campaign
from event.models import Event

ex = Event.objects.all()
for e in ex:
    e.save()

cx = Campaign.objects.all()
for c in cx:
    print c.pk
    c.save()


*/

/*

****** INCREASE HASHTAG max_length to 100: Done on Preview/Live 6/18/2009

*/


/*
-- Deployed 5/29/09

BEGIN;

ALTER TABLE event_stats ADD COLUMN num_views integer;
ALTER TABLE campaign_stats ADD COLUMN num_views integer;

CREATE INDEX "event_stats_num_views" ON "event_stats" ("num_views");
CREATE INDEX "campaign_stats_num_views" ON "campaign_stats" ("num_views");

COMMIT;


BEGIN;

UPDATE event_stats SET num_views=0;
UPDATE campaign_stats SET num_views=0;

COMMIT;

BEGIN;

ALTER TABLE event_stats ALTER COLUMN num_views SET NOT NULL;
ALTER TABLE campaign_stats ALTER COLUMN num_views SET NOT NULL;

COMMIT;


-- Deployed 5/20/09
BEGIN;

ALTER TABLE event_event ADD COLUMN price_text character varying(250);
ALTER TABLE event_event ADD COLUMN hashtag character varying(25);
ALTER TABLE event_event ADD COLUMN ticket_url character varying(200);
CREATE INDEX "event_event_ticket_url" ON "event_event" ("ticket_url");

COMMIT;
# python manage.py shell
from event.models import Event

for e in Event.objects.all():
    if e.price:
        e.price_text = u'$%s' % e.price
    super(Event, e).save()


*/

-----------------------------------------------------------------------------
-----------------------------------------------------------------------------
/*
-- Deployed 5/10/09
BEGIN;

ALTER TABLE event_event ADD COLUMN is_member_generated boolean;
ALTER TABLE event_event ALTER COLUMN is_member_generated SET DEFAULT false;
UPDATE event_event SET is_member_generated=false;
ALTER TABLE "event_event" ADD COLUMN
 "creator_id" integer 
 REFERENCES "registration_userprofile" ("id") DEFERRABLE INITIALLY DEFERRED;

COMMIT;

BEGIN;
ALTER TABLE event_event ALTER COLUMN is_member_generated SET NOT NULL;
CREATE INDEX "event_event_creator_id" ON "event_event" ("creator_id");
COMMIT;

BEGIN;

ALTER TABLE campaign_campaign ADD COLUMN url character varying(35);
CREATE INDEX "campaign_campaign_url" ON "campaign_campaign" ("url");

ALTER TABLE event_event ADD COLUMN url character varying(35);
CREATE INDEX "event_event_url" ON "event_event" ("url");

COMMIT;
*/

/*
BEGIN;

ALTER TABLE campaign_campaign ADD COLUMN is_event boolean;
UPDATE campaign_campaign SET is_event=False;
ALTER TABLE campaign_campaign ALTER COLUMN is_event SET NOT NULL;

COMMIT;
*/

/*
# python manage.py shell
from campaign.models import Campaign
Campaign.objects.all().update(is_event=False)
*/

------------------------------
------------------------------

/*
ALTER TABLE event_event ADD COLUMN mp3_url character varying(200);
ALTER TABLE event_eventchange ADD COLUMN mp3_url character varying(200);
CREATE INDEX "event_event_mp3_url" ON "event_event" ("mp3_url");
CREATE INDEX "event_eventchange_mp3_url" ON "event_eventchange" ("mp3_url");
*/

-- run manage.py syncdb

/*
ALTER TABLE event_event ADD COLUMN zip_code character varying(12);
ALTER TABLE event_event ALTER COLUMN zip_code SET STORAGE EXTENDED;
ALTER TABLE event_event ALTER COLUMN zip_code SET DEFAULT '02101'::character varying;
UPDATE event_event set zip_code = '02101';
ALTER TABLE event_event ALTER COLUMN zip_code SET NOT NULL;

ALTER TABLE event_eventchange ADD COLUMN zip_code character varying(12);
ALTER TABLE event_eventchange ALTER COLUMN zip_code SET STORAGE EXTENDED;
ALTER TABLE event_eventchange ALTER COLUMN zip_code SET NOT NULL;
ALTER TABLE event_eventchange ALTER COLUMN zip_code SET DEFAULT '02101'::character varying;
*/
