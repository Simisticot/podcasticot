-- Statements imported from the historical datastore._init_database method


create table if not exists user (
	id text not null primary key,
	email text not null unique
);

create table if not exists subscription (
	user_id text not null,
	feed_id text not null,
	primary key (user_id, feed_id),
	foreign key (user_id) references user(id),
	foreign key (feed_id) references podcast_feed(id)
);

create table if not exists podcast_feed (
	id text not null primary key,
	feed_url text not null, cover_art_url text
);

create table if not exists episode (
	episode_id text not null primary key,
	title text,
	description text,
	download_link text,
	published_date integer not null,
	feed_id text not null,
	length integer,
	foreign key (feed_id) references subscription(feed_id)
);

create table if not exists previous_listen (
	episode_id text not null,
	user_id text not null,
	seconds int not null,
	time int,
	primary key (episode_id, user_id),
	foreign key (episode_id) references episode(episode_id),
	foreign key (user_id) references user(id));
