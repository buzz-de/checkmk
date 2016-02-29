#!/usr/bin/python
# -*- encoding: utf-8; py-indent-offset: 4 -*-
# +------------------------------------------------------------------+
# |             ____ _               _        __  __ _  __           |
# |            / ___| |__   ___  ___| | __   |  \/  | |/ /           |
# |           | |   | '_ \ / _ \/ __| |/ /   | |\/| | ' /            |
# |           | |___| | | |  __/ (__|   <    | |  | | . \            |
# |            \____|_| |_|\___|\___|_|\_\___|_|  |_|_|\_\           |
# |                                                                  |
# | Copyright Mathias Kettner 2014             mk@mathias-kettner.de |
# +------------------------------------------------------------------+
#
# This file is part of Check_MK.
# The official homepage is at http://mathias-kettner.de/check_mk.
#
# check_mk is free software;  you can redistribute it and/or modify it
# under the  terms of the  GNU General Public License  as published by
# the Free Software Foundation in version 2.  check_mk is  distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;  with-
# out even the implied warranty of  MERCHANTABILITY  or  FITNESS FOR A
# PARTICULAR PURPOSE. See the  GNU General Public License for more de-
# tails. You should have  received  a copy of the  GNU  General Public
# License along with GNU Make; see the file  COPYING.  If  not,  write
# to the Free Software Foundation, Inc., 51 Franklin St,  Fifth Floor,
# Boston, MA 02110-1301 USA.

from mod_python import apache
import sys, os, pprint, __builtin__
import i18n
import sites
import livestatus
import modules
import defaults, config, login
from lib import *
from html_mod_python import html_mod_python, FinalizeRequest

# Main entry point for all HTTP-requests (called directly by mod_apache)
def handler(req, fields = None, is_profiling = False):
    if not is_profiling and os.path.exists(defaults.var_dir + "/profiling"):
        import cProfile
        # the profiler loses the memory about all modules. We need to hand over
        # the request object in the apache module.
        # Ubuntu: install python-profiler when using this feature
        profile_file = defaults.var_dir + "/profiling/multisite.profile"
        retcode = cProfile.runctx(
            "import index; "
            "index.handler(profile_req, profile_fields, is_profiling=True)",
            {'profile_req': req, 'profile_fields': fields}, {}, profile_file)
        file(profile_file + ".py", "w").write(
            "#!/usr/bin/python\n"
            "import pstats\n"
            "stats = pstats.Stats(%r)\n"
            "stats.sort_stats('time').print_stats()\n" % profile_file)
        os.chmod(profile_file + ".py", 0755)
        return apache.OK


    # Create an object that contains all data about the request and
    # helper functions for creating valid HTML. Parse URI and
    # store results in the request object for later usage.
    __builtin__.html = html_mod_python(req, fields)

    response_code = apache.OK
    try:
        config.load_config() # load multisite.mk etc.
        html.init_modes()

        # Make sure all plugins are avaiable as early as possible. At least
        # we need the plugins (i.e. the permissions declared in these) at the
        # time before the first login for generating auth.php.
        modules.load_all_plugins()

        # Get page handler.
        handler = modules.get_handler(html.myfile, page_not_found)

        # Some pages do skip authentication. This is done by adding
        # noauth: to the page hander, e.g. "noauth:run_cron" : ...
        if handler == page_not_found:
            handler = modules.get_handler("noauth:" + html.myfile, page_not_found)
            if handler != page_not_found:
                try:
                    handler()
                except Exception, e:
                    html.write(str(e))
                    if config.debug:
                        html.write(html.attrencode(format_exception()))
                raise FinalizeRequest()

        # Is the user set by the webserver? otherwise use the cookie based auth
        if not html.is_logged_in():
            config.auth_type = 'cookie'
            # When not authed tell the browser to ask for the password
            html.login(login.check_auth())
            if not html.is_logged_in():
                if fail_silently():
                    # While api call don't show the login dialog
                    raise MKUnauthenticatedException(_('You are not authenticated.'))

                # Redirect to the login-dialog with the current url as original target
                # Never render the login form directly when accessing urls like "index.py"
                # or "dashboard.py". This results in strange problems.
                if html.myfile != 'login':
                    html.http_redirect(defaults.url_prefix + 'check_mk/login.py?_origtarget=%s' %
                                                html.urlencode(html.makeuri([])))

                # Initialize the i18n for the login dialog. This might be overridden
                # later after user login
                i18n.localize(html.var("lang", config.get_language()))

                # This either displays the login page or validates the information submitted
                # to the login form. After successful login a http redirect to the originally
                # requested page is performed.
                login.page_login(plain_error())
                raise FinalizeRequest()
        else:
            # In case of basic auth the user is already known, but we still need to decide
            # whether or not the user is an automation user (which is allowed to use transid=-1)
            if html.var("_secret"):
                login.check_auth_automation()

        # Set all permissions, read site config, and similar stuff
        config.login(html.user)
        html.load_help_visible()

        # Initialize the multiste i18n. This will be replaced by
        # language settings stored in the user profile after the user
        # has been initialized
        i18n.localize(html.var("lang", config.get_language()))

        # All plugins might have to be reloaded due to a language change
        modules.load_all_plugins()

        # User allowed to login at all?
        if not config.may("general.use"):
            reason = _("You are not authorized to use Check_MK Multisite. Sorry. "
                       "You are logged in as <b>%s</b>.") % config.user_id
            if len(config.user_role_ids):
                reason += _("Your roles are <b>%s</b>. " % ", ".join(config.user_role_ids))
            else:
                reason += _("<b>You do not have any roles.</b> ")
            reason += _("If you think this is an error, "
                        "please ask your administrator to check the permissions configuration.")

            if config.auth_type == 'cookie':
                reason += _('<p>You have been logged out. Please reload the page to re-authenticate.</p>')
                login.del_auth_cookie()

            raise MKAuthException(reason)

        handler()

    except FinalizeRequest, e:
        response_code = e.status

    except (MKUserError, MKAuthException, MKUnauthenticatedException, MKConfigError, MKGeneralException,
            livestatus.MKLivestatusNotFoundError, livestatus.MKLivestatusException), e:
        ty = type(e)
        if ty == livestatus.MKLivestatusNotFoundError:
            title       = _("Data not found")
            plain_title = _("Livestatus-data not found")
        elif isinstance(e, livestatus.MKLivestatusException):
            title       = _("Livestatus problem")
            plain_title = _("Livestatus problem")
        else:
            title       = e.title
            plain_title = e.plain_title

        if plain_error():
            html.write("%s: %s\n" % (plain_title, e))
        elif not fail_silently():
            html.header(title)
            html.show_error(e)
            html.footer()


        # Some exception need to set a specific HTTP status code
        if ty == MKUnauthenticatedException:
            response_code = apache.HTTP_UNAUTHORIZED
        elif ty == livestatus.MKLivestatusException:
            response_code = apache.HTTP_BAD_GATEWAY

        if ty in [MKConfigError, MKGeneralException]:
            logger(LOG_ERR, _("%s: %s") % (plain_title, e))

    except (apache.SERVER_RETURN,
            (apache.SERVER_RETURN, apache.HTTP_UNAUTHORIZED),
            (apache.SERVER_RETURN, apache.HTTP_MOVED_TEMPORARILY)):
        release_all_locks()
        sites.disconnect()
        html.finalize(is_error=True)
        raise

    except Exception, e:
        html.unplug()
        import traceback
        msg = "%s %s: %s" % (html.request_uri(), _('Internal error'), traceback.format_exc())
        if type(msg) == unicode:
            msg = msg.encode('utf-8')
        logger(LOG_ERR, msg)
        if plain_error():
            html.write(_("Internal error") + ": %s\n" % html.attrencode(e))
        elif not fail_silently():
            modules.get_handler("gui_crash")()
        response_code = apache.OK

    release_all_locks()
    sites.disconnect()
    html.finalize()
    return response_code


# Ajax-Functions want no HTML output in case of an error but
# just a plain server result code of 500
def fail_silently():
    return html.has_var("_ajaxid")

# Webservice functions may decide to get a normal result code
# but a text with an error message in case of an error
def plain_error():
    return html.has_var("_plain_error")


def page_not_found():
    if html.has_var("_plain_error"):
        html.write(_("Page not found"))
    else:
        html.header(_("Page not found"))
        html.show_error(_("This page was not found. Sorry."))
    html.footer()


# prepare local-structure within OMD sites
# FIXME: Still needed?
def init_sys_path():
    if defaults.omd_root:
        local_module_path = defaults.omd_root + "/local/share/check_mk/web/htdocs"
        local_locale_path = defaults.omd_root + "/local/share/check_mk/locale"
        if local_module_path not in sys.path:
            sys.path[0:0] = [ local_module_path, defaults.web_dir + "/htdocs" ]


# Early initialization upon first start of the application by the server
def initialize():
    init_sys_path()
    modules.init_modules()


# Run the global application initialization code here. It is called
# only once during the startup of the application server.
initialize()
