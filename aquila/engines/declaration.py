# Declaratively defining the intelligent tasks and how exactly will it operate on the state to achieve the desired
# state (which is also specified here) from the current state.
#
# These declarations will be compiled to a binary and then executed as/when neccessary. These declarations can also include
# `agent` "definitions" and target behaviours. The point of this is so that these intelligent tasks can be deployed to
# reproducible environments like `dev`, `demo`, `prod`, etc. - again, much like how terraform works
#
# HEAVYILY inspired from terraform and it's HCL language
#
# Also need to have a way to perform ** evaluation **, to check whether it is able to reliably achieve what was wanted
# ********* -> this could be a potential source of revenue as well
