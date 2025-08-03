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
#
#
# One point on how is it different than a "workflow" -> a workflow is not aware of it's own existence and cannot
# manipulate it's own self or its own state in the middle.
#
# It also kind of needs to have this continous awareness of the state of the environment

"""

task "something" {
    import old_init_task {

        # In case there's replacements for "env.*" variables
        x = l           # x in 'old_init_task' definition, actually means 'l' in task.somethings' env case

    }

    <the environment which is being operated upon is embedded>

    # The objective is to define this target state in a task
    target_state = {
        a = x,
        b = y,
        etc.
    },

    # Again, inputs are not given, because env is embedded,
    # and `__run__` defines the manual things you'd want to do in this task
    __run__ = task.old_init_task()

    __agent__ = {
        <predfined ghost agent to be called by its name>,
        target_state = {
            a = x - 1,
            b = y - 1
        }
    },

    # this could also mean manual updates to the state
    __run__ = {
        x = a + 1
        y = b + 1
    }
}
"""

#
# Actually, I think I can use Pydantic class - and it's mechanisms - to declaratively define things like "target state" and hence
# convert the above into a readable pydantic-like thing maybe?

# from pydantic import BaseModel

# class Task(BaseModel):
#     name = "something"
    
#     imports = {
#         "old_init_task": {
#             "x": "l"
#         }
#     },
    
#     target_state = {
#         "a": "x",
#         "b": "y"
#     }

#     __run__ = "old_init_task",

#     __agent__ = {
#         "ghost-agent": {
#             "target_state": {

#             }
#         }
#     }

# ^ Ugh that is incomplete cuz it gets frustrating to write very quickly to me, it'll be nice if I could say write a plugin in python
# for something that already exists - like maybe Pulumi? Since it has a Python SDK unlike Terraform

# That would also give me things like state management, graph creation, diff management, etc. out of the box
