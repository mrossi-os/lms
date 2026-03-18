FROM frappe/bench:latest

USER frappe
RUN pip install "setuptools<82"

RUN mkdir -p /home/frappe/bench-data/frappe-bench
WORKDIR /home/frappe/bench-data/frappe-bench
