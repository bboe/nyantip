CREATE TABLE IF NOT EXISTS `actions` (
  `action` enum('accept','decline','history','info','register','tip','withdraw') NOT NULL,
  `amount` decimal(17,8) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT NOW(),
  `destination` varchar(34) DEFAULT NULL,
  `message_id` varchar(10) NOT NULL,
  `message_kind` enum('comment', 'message') NOT NULL,
  `message_timestamp` timestamp NOT NULL,
  `source` varchar(20) NOT NULL,
  `status` enum('completed','declined','expired','failed','pending') NOT NULL,
  `transaction_id` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`message_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `users` (
  `address` varchar(34) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT NOW(),
  `username` varchar(20) NOT NULL,
  PRIMARY KEY (`username`),
  UNIQUE KEY `address` (`address`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
