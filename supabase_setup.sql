-- 스마트 냉장고: Supabase 테이블 만들기 (5단계 사용자별 개인 냉장고)
-- Supabase 대시보드 → SQL Editor → 이 내용을 붙여 넣고 Run 한 번.
-- 앱은 service_role 키로 서버에서만 접근한다. RLS를 켜고 정책을 만들지 않아서
-- 브라우저용 anon 키로는 아무 행도 읽거나 쓸 수 없다.

create table if not exists app_users (
    nickname   text primary key,
    pw_hash    text not null,              -- 비밀번호 원문이 아니라 salt$PBKDF2 해시
    created_at timestamptz default now()
);

create table if not exists user_data (
    nickname   text references app_users(nickname) on delete cascade,
    name       text not null,              -- "fridge" / "shopping" / "usage_log"
    data       jsonb not null,
    updated_at timestamptz default now(),
    primary key (nickname, name)
);

create table if not exists login_tokens (
    token_hash text primary key,           -- 로그인 유지 토큰의 해시 (토큰 원문은 브라우저에만)
    nickname   text references app_users(nickname) on delete cascade,
    created_at timestamptz default now()
);

alter table app_users    enable row level security;
alter table user_data    enable row level security;
alter table login_tokens enable row level security;
