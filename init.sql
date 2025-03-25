ALTER USER 'bcfg_sa'@'%' IDENTIFIED WITH mysql_native_password BY 'root_password';
GRANT ALL PRIVILEGES ON *.* TO 'bcfg_sa'@'%' WITH GRANT OPTION;
FLUSH PRIVILEGES;
