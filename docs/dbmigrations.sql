BEGIN TRANSACTION;

ALTER TABLE campaign_campaign ADD COLUMN edited_on timestamp with time zone;

/**

	Run manage.py syncdb

**/

/**
alter table "registration_userprofile" add column "avatar_image" varchar(250) NULL;
alter table "registration_userprofile" add column "avatar" varchar(250) NULL;
alter table "registration_userprofile" add column "avatar_width" integer CHECK ("avatar_width" >= 0) NULL;
alter table "registration_userprofile" add column "avatar_height" integer CHECK ("avatar_height" >= 0) NULL;

alter table "artist_artistprofile" add column "website" varchar(150) NULL;
**/

COMMIT;

