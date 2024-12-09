#!/bin/bash
SID="$(curl -X GET http://localhost:5000/new_session)"

echo $SID
