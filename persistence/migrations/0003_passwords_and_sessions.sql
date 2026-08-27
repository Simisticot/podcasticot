alter table user add password_hash text not null default 'no set password';

create table if not exists session (
	token_hash text primary key,
	user_id text not null,
	expires_at timestamp not null
);
