import subprocess


def execute_command(cmds, env=None, cwd=None, logger=None, err_prefix=None) -> str:
    """ Executes a command as a subprocess
    If the return code of the call is 0 then return stdout otherwise
    raise a RuntimeError.  If logger is specified then write the exception
    to the logger otherwise this call will remain silent.
    :param cmds:list of commands to pass to subprocess.run
    :param env: environment to run the command with
    :param cwd: working directory for the command
    :param logger: a logger to use if errors occure
    :param err_prefix: an error prefix to allow better tracing through the error message
    :return: stdout string if successful
    :raises RuntimeError: if the return code is not 0 from suprocess.run
    """

    results = subprocess.run(cmds,
                             env=env,
                             cwd=cwd,
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE)
    if results.returncode != 0:
        err_prefix = err_prefix if err_prefix is not None else "Error executing command"
        err_message = "\n{}: Below Command failed with non zero exit code.\n" \
                      "Command:{} \nStderr:\n{}\n".format(err_prefix,
                                                          results.args,
                                                          results.stderr)
        if logger:
            logger.exception(err_message)
            raise RuntimeError()
        else:
            raise RuntimeError(err_message)

    return results.stdout.decode('utf-8')
