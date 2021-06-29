# syntax=docker/dockerfile:1

FROM python:3.9

ADD requirements.txt /
ADD client.py /
ADD models.py /
ADD p2p.py /
ADD protocols.py /
ADD defaults.py /

RUN pip3 install -r requirements.txt

CMD [ "python3", "-m", "p2p.py"]