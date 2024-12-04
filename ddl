CREATE TABLE Users (
    id BIGINT AUTO_INCREMENT NOT NULL COMMENT '유저id',
    username VARCHAR(50) NULL COMMENT '이름',
    phone VARCHAR(20) NULL COMMENT '휴대폰번호',
    total_balance INT DEFAULT 0 NULL COMMENT '보유금액',
    orderable_balance INT DEFAULT 0 NULL COMMENT '주문가능금액',
    wallet VARCHAR(255) NULL COMMENT '지갑주소',
    created_at DATETIME NULL COMMENT '생성시간',
    PRIMARY KEY (id)
) COMMENT='유저';

CREATE TABLE Property_Detail (
    id BIGINT AUTO_INCREMENT NOT NULL COMMENT '방id',
    detail_floor BIGINT NULL COMMENT '층수',
    room_cnt VARCHAR(100) NULL COMMENT '방수/욕실수',
    maintenance_cost INT DEFAULT 0 NULL COMMENT '관리비',
    home_size VARCHAR(100) NULL COMMENT '평수',
    home_photos VARCHAR(255) NULL COMMENT '집사진 [static경로.jpeg]',
    legalDocs VARCHAR(255) NULL COMMENT '법적문서 [static경로.jpeg]',
    legalNotice TINYINT DEFAULT 0 NULL COMMENT '동의여부 (0: 미동의, 1: 동의)',
    property_id BIGINT NULL COMMENT '건물id',
    subscription_status ENUM('pending', 'fulfilled') DEFAULT 'pending' COMMENT '청약 상태',
    PRIMARY KEY (id)
) COMMENT='건물 매물 정보';

CREATE TABLE Building (
    id BIGINT NOT NULL COMMENT '건물id',
    name VARCHAR(100) NOT NULL COMMENT '건물이름',
    token_supply INT NOT NULL COMMENT '건물에 할당된 총 토큰 수',
    created_at DATETIME NOT NULL COMMENT '건물등록시간',
    price FLOAT NULL COMMENT '최근 거래된 가격',
    address VARCHAR(100) NOT NULL COMMENT '건물실주소',
    building_code VARCHAR(100) NOT NULL COMMENT '건물주소 코드',
    platArea VARCHAR(100) NOT NULL COMMENT '대지면적',
    bcRat VARCHAR(100) NOT NULL COMMENT '건폐율',
    totArea VARCHAR(100) NOT NULL COMMENT '연면적',
    vlRat VARCHAR(100) NOT NULL COMMENT '용적률',
    property_photo VARCHAR(100) NULL COMMENT '대표사진 [static경로.jpeg]',
    Lat FLOAT NULL COMMENT '위도',
    Lng FLOAT NULL COMMENT '경도',
    PRIMARY KEY (id)
) COMMENT='건물 정보 테이블';

CREATE TABLE Ownerships (
    id BIGINT AUTO_INCREMENT NOT NULL COMMENT '소유내역id',
    quantity INT NULL COMMENT '소유량',
    tradeable_tokens INT DEFAULT 0 NULL COMMENT '거래가능토큰수',
    buy_price INT DEFAULT 0 NULL COMMENT '평단가',
    created_at DATETIME NULL COMMENT '소유 내역 생성 시간',
    user_id BIGINT NULL COMMENT '유저id',
    property_detail_id BIGINT NULL COMMENT '방id',
    PRIMARY KEY (id),
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_property_detail FOREIGN KEY (property_detail_id) REFERENCES Property_Detail (id) ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT='소유권';

CREATE TABLE Order_Archive (
    id BIGINT AUTO_INCREMENT NOT NULL COMMENT '주문id',
    order_type ENUM('buy', 'sell') NULL COMMENT '주문유형',
    price_per_token INT NULL COMMENT '토큰당 가격',
    quantity INT NULL COMMENT '거래 수량',
    status ENUM('fulfilled', 'cancelled', 'normal') NULL COMMENT '최종 상태',
    created_at DATETIME NULL COMMENT '주문 체결 시간',
    user_id BIGINT NULL COMMENT '유저id',
    property_detail_id BIGINT NULL COMMENT '방id',
    PRIMARY KEY (id),
    CONSTRAINT fk_order_user FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_order_property FOREIGN KEY (property_detail_id) REFERENCES Property_Detail (id) ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT='주문기록';

CREATE TABLE Property_History (
    id BIGINT AUTO_INCREMENT NOT NULL COMMENT '기록id',
    recorded_date DATETIME NULL COMMENT '날짜',
    price INT NULL COMMENT '가격',
    quantity INT NULL DEFAULT 0 COMMENT '체결 수량',
    property_detail_id BIGINT NULL COMMENT '방id',
    PRIMARY KEY (id),
    CONSTRAINT fk_history_property FOREIGN KEY (property_detail_id) REFERENCES Property_Detail (id) ON DELETE CASCADE ON UPDATE CASCADE
) COMMENT='건물날짜별정보';