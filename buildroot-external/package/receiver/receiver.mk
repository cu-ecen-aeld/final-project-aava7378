################################################################################
#
# receiver
#
################################################################################

RECEIVER_VERSION = 1.0
RECEIVER_SITE = $(TOPDIR)/../final-project-aava7378/pi4
RECEIVER_SITE_METHOD = local
RECEIVER_LICENSE = MIT
RECEIVER_LICENSE_FILES =

define RECEIVER_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/receiver.py \
		$(TARGET_DIR)/usr/bin/receiver.py
endef

$(eval $(generic-package))
