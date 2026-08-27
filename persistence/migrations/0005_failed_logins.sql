create table if not exists failed_login (
	user_id integer not null,
	failed_at integer not null,
	foreign key (user_id) references user(id)
);
