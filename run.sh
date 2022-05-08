need_build=$(docker inspect askrey_ex_img)

if [[ "$need_build" == "[]" ]]; then
    docker build -t askrey_ex_img .
fi

docker run -u=$(id -u $USER):$(id -g $USER) \
           -e DISPLAY=$DISPLAY \
           -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
           -v $(pwd)/:$(pwd) \
           --rm \
           askrey_ex_img
