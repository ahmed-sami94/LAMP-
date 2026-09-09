<?php
// Secrets arrive on stdin, not in process arguments or an HTTP-accessible file.
$request = json_decode(stream_get_contents(STDIN), true, 32, JSON_THROW_ON_ERROR);
$script = $request['script'];
$argv = array_merge([$script], $request['arguments']);
$_SERVER['argv'] = $argv;
$_SERVER['argc'] = count($argv);
$argc = count($argv);
require $script;
