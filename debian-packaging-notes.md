For older systems (buster/bullseye and ubuntu focal) uncomment the packages in debian-requirements and comment python3-jwt in debian/control before running debuild.

For newer then bookworm (ubuntu noble/debian sid) comment upgrade pip line in rules.

TODO:

Rework it. Virtual env may not be needed in newer Debian/Ubuntu



