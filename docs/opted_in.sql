select b.username, b.first_name, b.last_name, b.email, 
case 
 when a.is_artist = 't' then 'artist'
 else 'member'
end 
as "user type"
from registration_userprofile a, auth_user b
where
a.user_id = b.id and
a.has_opted_in = true
order by username