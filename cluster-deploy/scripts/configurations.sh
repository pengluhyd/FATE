#!/bin/bash

user=app 
dir=/data/projects/fate 
mysqldir=/data/projects/common/mysql/mysql-8.0 
javadir=/data/projects/common/jdk/jdk1.8 
venvdir=/data/projects/eggroll/venv
redisip=(A.redisip B.redisip)
redispass=fateboard
partylist=(partyA.id partyB.id)
JDBC0=(A.MS-ip A.dbname A.user A.password) 
JDBC1=(B.MS-ip B.dbname B.user B.password) 
fateflowdb0=(A.FF-ip A.dbname A.user A.password) 
fateflowdb1=(B.FF-ip B.dbname B.user B.password) 
iplist=(A.F-ip A.MS-ip A.P-ip A.R-ip A.FB-ip B.F-ip B.MS-ip B.P-ip B.R-ip B.FB-ip)
iplist0=(A.F-ip A.MS-ip A.P-ip A.R-ip A.FB-ip A.E1-ip A.E2-ip A.E3-ip...)
iplist1=(B.F-ip B.MS-ip B.P-ip B.R-ip B.FB-ip B.E1-ip B.E2-ip B.E3-ip...)
fateboard0=(A.FB-ip)
fateboard1=(B.FB-ip)
eggautocompile=true
fedlist0=(A.F-ip)
fedlist1=(B.F-ip)
meta0=(A.MS-ip)
meta1=(B.MS-ip)
proxy0=(A.P-ip)
proxy1=(B.P-ip)
roll0=(A.R-ip)
roll1=(B.R-ip)
egglist0=(A.E1-ip A.E2-ip A.E3-ip...)
egglist1=(B.E1-ip B.E2-ip B.E3-ip...) 
fllist0=(A.FL-ip)
fllist1=(B.FL-ip)
serving0=(A.S1-ip A.S2-ip)
serving1=(B.S1-ip B.S2-ip)
exchangeip=exchangeip 